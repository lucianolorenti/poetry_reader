import os
import logging
import re
import wave
from glob import glob
from typing import Optional, Callable
import unicodedata

from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.audio.AudioClip import concatenate_audioclips
from langdetect import detect

from .ttsgenerator import get_tts
from .video_generator import create_video_with_subtitles
from .utils import parse_md_file

LOGGER = logging.getLogger(__name__)


def detect_language(text: str) -> str:
    """Detect language code for `text`. Prefers `langdetect` if available,
    otherwise uses a simple heuristic checking for accented characters.
    Returns a 2-letter code like 'es' or 'en'.
    """
    if not text or not text.strip():
        return "en"
    if detect:
        try:
            code = detect(text)
            return code.split("-")[0]
        except Exception:
            pass
    spanish_chars = set("áéíóúñÁÉÍÓÚÑ¿¡")
    if any(c in spanish_chars for c in text):
        return "es"
    return "en"


def normalize_text_for_tts(text: str) -> str:
    """Remove accent marks from text for TTS models with limited vocabularies.

    Converts: á->a, é->e, í->i, ó->o, ú->u, ñ->ñ (keep ñ)
    This helps with TTS models that don't support accented characters.
    """
    nfd = unicodedata.normalize("NFD", text)
    result = []
    for char in nfd:
        if char in "ñÑ":
            result.append(char)
        elif not unicodedata.combining(char):
            result.append(char)
    return "".join(result)


def sanitize_filename(s: str) -> str:
    return "".join(c for c in s if c.isalnum() or c in (" ", "-", "_")).rstrip()


def split_text_into_sentences(text: str):
    parts = re.split(r"(?<=[\.\?!])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def split_text_into_lines(text: str):
    """Split text preserving original line breaks. Returns list of lines including empty lines.

    We preserve empty lines so the video can insert short pauses where appropriate.
    """
    if text is None:
        return []
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return lines


def group_lines_into_blocks(lines):
    """Group poem lines into text and silence blocks.

    - Consecutive non-empty lines -> one text block
    - Each empty line -> one silence block (for a pause between stanzas)
    """
    blocks = []
    current_lines = []

    for line in lines:
        if line.strip():
            # Non-empty: accumulate in current text block
            current_lines.append(line)
        else:
            # Empty line: close current text block (if any) and add a silence block
            if current_lines:
                blocks.append({"type": "text", "lines": current_lines})
                current_lines = []
            blocks.append({"type": "silence", "lines": [""]})

    # Flush last pending text block
    if current_lines:
        blocks.append({"type": "text", "lines": current_lines})

    return blocks


def allocate_durations_for_lines(lines, total_duration):
    """Allocate total_duration across lines proportionally to their length.

    This is a heuristic for per-verse timing inside a TTS block.
    """
    n = len(lines)
    if n == 0 or total_duration <= 0:
        return [0.0] * n

    # Use character length (after strip) as weight; fall back to 1 to avoid zeros
    weights = [len(line.strip()) or 1 for line in lines]
    total_weight = sum(weights)

    if total_weight <= 0:
        # Equal distribution if everything is empty / weird
        base = total_duration / n
        durations = [base] * n
        # Adjust last one to absorb rounding error
        durations[-1] = max(0.0, total_duration - sum(durations[:-1]))
        return durations

    durations = []
    acc = 0.0
    for i, w in enumerate(weights):
        if i == n - 1:
            # Last line: absorb any rounding error
            dur = max(0.0, total_duration - acc)
        else:
            dur = total_duration * (w / total_weight)
            acc += dur
        durations.append(dur)

    return durations


def write_silence_wav(path: str, duration: float = 0.6, framerate: int = 22050):
    """Write a mono 16-bit silent WAV file of given duration (seconds)."""
    n_frames = int(duration * framerate)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(b"\x00\x00" * n_frames)


def main(
    input_dir: str = "input",
    out_dir: str = "output",
    image_path: Optional[str] = None,
    gradient_palette: Optional[str] = None,
    add_particles: bool = True,
    font_size: int = 80,
    fade_duration: float = 0.5,
    force_lang: Optional[str] = None,
    fps: int = 30,
    num_particles: int = 80,
    tts_backend: str = "qwen3",
    tts_model: Optional[str] = None,
    tts_reference_wav: Optional[str] = None,
    device: str = "auto",
    tts_model_size: str = "1.7B",
    resolution: tuple = (1080, 1920),
    tiktok_mode: bool = True,
    zoom_background: bool = True,
    upload_callback=None,
):
    """Main video generation pipeline reading `.md` files from `input_dir`.

    Optimized for TikTok with vertical 9:16 format, high-quality TTS,
    and professional visual effects.

    Each `.md` must have a title and author in the first lines as:
    Titulo: My Title
    Autor: Ada

    Then the poem content from the next line onward.

    Args:
        upload_callback: Optional callback function called after each video is generated.
                        Receives dict with: video_path, title, author, text, base_name
    """
    os.makedirs(out_dir, exist_ok=True)

    pattern = os.path.join(input_dir, "*.md")
    files = sorted(glob(pattern))

    if not files:
        print(f"No se encontraron archivos .md en: {os.path.abspath(input_dir)}")
        return

    tts_cache = {}

    for idx, path in enumerate(files):
        try:
            title, author, text = parse_md_file(path)
        except Exception as e:
            print(f"Error al parsear {path}: {e}")
            continue

        raw_name = f"{idx + 1}_{title}"
        safe_name = sanitize_filename(raw_name)
        if len(safe_name) > 80:
            safe_name = safe_name[:80]
        base_name = safe_name

        audio_frag_dir = os.path.join(out_dir, base_name + "_frags")
        os.makedirs(audio_frag_dir, exist_ok=True)

        if force_lang:
            lang = force_lang
        else:
            lang = detect_language(text)

        tts_key = f"{tts_backend}:{lang}:{tts_model or ''}:{tts_reference_wav or ''}:{device}:{tts_model_size}"
        if tts_key not in tts_cache:
            tts_cache[tts_key] = get_tts(
                backend=tts_backend,
                lang=lang,
                model_name=tts_model,
                reference_wav_path=tts_reference_wav,
                device=device,
                model_size=tts_model_size,
            )
        print(tts_key)
        tts = tts_cache[tts_key]

        # Split into raw lines and group into blocks
        lines = split_text_into_lines(text)
        blocks = group_lines_into_blocks(lines)

        fragments = []
        subtitles = []
        start_time = 0.0

        # Prepare batch synthesis: collect all text blocks and their paths
        texts_to_synthesize = []
        paths_to_synthesize = []
        block_tts_index = {}  # block_idx -> index into texts_to_synthesize

        for block_idx, block in enumerate(blocks):
            frag_path = os.path.join(audio_frag_dir, f"block_{block_idx + 1}.wav")
            if block["type"] == "text":
                # Join lines so TTS sees the whole stanza/phrase
                block_text = "\n".join(block["lines"]).strip()
                texts_to_synthesize.append(block_text)
                paths_to_synthesize.append(frag_path)
                block_tts_index[block_idx] = len(texts_to_synthesize) - 1
            else:
                # Silence block, no TTS needed
                block_tts_index[block_idx] = None

        # Generate all text-block audios in a single batch for consistent voice
        if texts_to_synthesize:
            LOGGER.info(
                f"Synthesizing {len(texts_to_synthesize)} text blocks in batch..."
            )
            LOGGER.info(f"Text blocks: {texts_to_synthesize}")
            LOGGER.info(f"Output paths: {paths_to_synthesize}")
            tts.synthesize_batch_to_files(
                texts=texts_to_synthesize,
                out_paths=paths_to_synthesize,
            )
            # Verify files were created
            for path in paths_to_synthesize:
                if os.path.exists(path):
                    size = os.path.getsize(path)
                    LOGGER.info(f"Generated file: {path}, size: {size} bytes")
                else:
                    LOGGER.error(f"Missing file: {path}")

        # Process all blocks in order (silences and synthesized text blocks)
        LOGGER.info(f"Processing {len(blocks)} blocks...")
        for block_idx, block in enumerate(blocks):
            frag_path = os.path.join(audio_frag_dir, f"block_{block_idx + 1}.wav")

            if block["type"] == "silence":
                # Silence block: fixed pause
                write_silence_wav(frag_path, duration=0.5)
                clip = AudioFileClip(frag_path)
                dur = clip.duration
                LOGGER.info(f"Silence block {block_idx}: duration={dur:.2f}s")
                clip = clip.subclipped(0, dur)
                fragments.append(clip)
                subtitles.append({"text": "", "start": start_time, "duration": dur})
                start_time += dur
                continue

            # Text block
            tts_idx = block_tts_index.get(block_idx)
            if tts_idx is None:
                LOGGER.error(f"No TTS index for text block {block_idx}")
                continue

            if not os.path.exists(frag_path):
                LOGGER.error(f"Audio file missing for block {block_idx}: {frag_path}")
                continue

            file_size = os.path.getsize(frag_path)
            LOGGER.info(
                f"Text block {block_idx}: loading {frag_path} ({file_size} bytes)"
            )
            clip = AudioFileClip(frag_path)
            LOGGER.info(
                f"Text block {block_idx}: loaded, duration={clip.duration:.2f}s, fps={clip.fps}"
            )

            dur = clip.duration
            LOGGER.info(
                f"Text block {block_idx}: final duration={dur:.2f}s, lines={len(block['lines'])}"
            )

            clip = clip.subclipped(0, dur)
            fragments.append(clip)

            # Advanced coordination: distribute block duration across its lines (verses)
            line_durations = allocate_durations_for_lines(block["lines"], dur)

            line_start = start_time
            for line, line_dur in zip(block["lines"], line_durations):
                if line_dur <= 0:
                    continue
                subtitles.append(
                    {"text": line, "start": line_start, "duration": line_dur}
                )
                line_start += line_dur

            # Advance global time by the whole block duration
            start_time += dur

        if fragments:
            total_duration = sum(c.duration for c in fragments)
            # Check sample rates are consistent
            sample_rates = [c.fps for c in fragments]
            LOGGER.info(f"Fragment sample rates: {sample_rates}")
            if len(set(sample_rates)) > 1:
                LOGGER.warning(
                    f"WARNING: Different sample rates detected: {set(sample_rates)}"
                )

            LOGGER.info(
                f"Concatenating {len(fragments)} fragments, total duration: {total_duration:.2f}s"
            )
            final_audio = concatenate_audioclips(fragments)
            final_audio_path = os.path.join(out_dir, base_name + ".wav")
            LOGGER.info(f"Writing final audio to {final_audio_path}")
            # Write with explicit codec and parameters to avoid truncation
            final_audio.write_audiofile(
                final_audio_path,
                codec="pcm_s16le",  # Standard WAV codec
                fps=24000,  # Match TTS sample rate
                nbytes=2,  # 16-bit
                buffersize=2000,
            )
            LOGGER.info(f"Final audio duration: {final_audio.duration:.2f}s")
            # Verify file was written correctly
            if os.path.exists(final_audio_path):
                file_size = os.path.getsize(final_audio_path)
                LOGGER.info(f"Final audio file size: {file_size} bytes")
            for c in fragments:
                c.close()
            final_audio.close()

            video_path = os.path.join(out_dir, base_name + ".mp4")
            create_video_with_subtitles(
                audio_path=final_audio_path,
                subtitles=subtitles,
                out_path=video_path,
                title=title,
                author=author,
                image_path=image_path,
                fps=fps,
                resolution=resolution,
                fontsize=font_size,
                gradient_palette=gradient_palette,
                add_particles=add_particles,
                num_particles=num_particles,
                fade_duration=fade_duration,
                tiktok_mode=tiktok_mode,
                zoom_background=zoom_background,
                add_sparkles=True,
            )

            # Llamar al callback de upload si está configurado
            if upload_callback:
                try:
                    upload_callback(
                        {
                            "video_path": video_path,
                            "title": title,
                            "author": author,
                            "text": text,
                            "base_name": base_name,
                        }
                    )
                except Exception as e:
                    LOGGER.error(f"Error en upload callback: {e}")

            try:
                for f in os.listdir(audio_frag_dir):
                    os.remove(os.path.join(audio_frag_dir, f))
                os.rmdir(audio_frag_dir)
            except Exception:
                pass

    print(f"Generados videos en: {os.path.abspath(out_dir)}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Genera audios y videos desde archivos .md en input"
    )
    parser.add_argument(
        "input_dir", help="Directorio de entrada con .md files", default="input"
    )
    parser.add_argument("--out", help="Directorio de salida", default="output")
    parser.add_argument("--image", help="Imagen de fondo para videos", default=None)
    parser.add_argument(
        "--gradient-palette", help="Paleta de colores del gradiente", default=None
    )
    parser.add_argument(
        "--no-particles", action="store_true", help="Desactivar partículas"
    )
    parser.add_argument("--font-size", type=int, default=80, help="Tamaño de fuente")
    parser.add_argument(
        "--fade-duration", type=float, default=0.5, help="Duración del fade"
    )
    parser.add_argument("--force-lang", help="Forzar idioma (es/en)", default=None)
    parser.add_argument("--fps", type=int, default=30, help="Frames por segundo")
    parser.add_argument(
        "--num-particles", type=int, default=80, help="Número de partículas"
    )
    parser.add_argument("--tts-model", help="Modelo TTS", default=None)
    parser.add_argument(
        "--tts-reference-wav", help="WAV de referencia para TTS", default=None
    )
    parser.add_argument("--device", default="auto", help="Device para TTS")
    parser.add_argument(
        "--tts-model-size", default="1.7B", help="Tamaño del modelo TTS"
    )
    parser.add_argument(
        "--vertical", action="store_true", default=True, help="Formato vertical"
    )
    parser.add_argument(
        "--no-zoom", action="store_true", help="Desactivar zoom de fondo"
    )
    args = parser.parse_args()

    resolution = (1080, 1920) if args.vertical else (1280, 720)

    main(
        input_dir=args.input_dir,
        out_dir=args.out,
        image_path=args.image,
        gradient_palette=args.gradient_palette,
        add_particles=not args.no_particles,
        font_size=args.font_size,
        fade_duration=args.fade_duration,
        force_lang=args.force_lang,
        fps=args.fps,
        num_particles=args.num_particles,
        tts_backend="qwen3",
        tts_model=args.tts_model,
        tts_reference_wav=args.tts_reference_wav,
        device=args.device,
        tts_model_size=args.tts_model_size,
        resolution=resolution,
        tiktok_mode=True,
        zoom_background=not args.no_zoom,
    )
