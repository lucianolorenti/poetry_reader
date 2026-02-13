import os
import logging
from glob import glob
from tqdm import tqdm
from typing import Optional
import unicodedata


from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.audio.AudioClip import concatenate_audioclips
from .ttsgenerator import get_tts


from langdetect import detect

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


from .video_generator import create_video_with_subtitles


def sanitize_filename(s: str) -> str:
    return "".join(c for c in s if c.isalnum() or c in (" ", "-", "_")).rstrip()


def split_text_into_sentences(text: str):
    import re

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


def write_silence_wav(path: str, duration: float = 0.6, framerate: int = 22050):
    """Write a mono 16-bit silent WAV file of given duration (seconds)."""
    import wave

    n_frames = int(duration * framerate)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(b"\x00\x00" * n_frames)


def parse_md_file(path: str):
    """Parse a markdown file with the expected format:
    First non-empty line: starts with 'Titulo:' or 'Título:' or 'Title:' -> title
    Second non-empty line: starts with 'Autor:' or 'Author:' -> author
    Remaining lines: poem content.

    Returns (title, author, content_str).
    """
    with open(path, "r", encoding="utf-8") as f:
        lines = [l.rstrip("\n\r") for l in f.readlines()]

    stripped = [ln.strip() for ln in lines]
    non_empty = [ln for ln in stripped if ln != ""]

    title = None
    author = None
    content_lines = []

    if len(non_empty) >= 1:
        first = non_empty[0]
        if ":" in first:
            key, val = first.split(":", 1)
            if key.strip().lower() in ("titulo", "título", "title"):
                title = val.strip()

    if len(non_empty) >= 2:
        second = non_empty[1]
        if ":" in second:
            key, val = second.split(":", 1)
            if key.strip().lower() in ("autor", "author"):
                author = val.strip()

    if title is None or author is None:
        for ln in stripped[:4]:
            if ln and ":" in ln:
                key, val = ln.split(":", 1)
                k = key.strip().lower()
                if title is None and k in ("titulo", "título", "title"):
                    title = val.strip()
                if author is None and k in ("autor", "author"):
                    author = val.strip()

    start_idx = 0
    header_count = 0
    for i, ln in enumerate(lines):
        if ln.strip() == "":
            continue
        if ":" in ln and header_count < 2:
            header_count += 1
            start_idx = i + 1
            continue
        if header_count >= 2:
            start_idx = i
            break
    if header_count < 2:
        count = 0
        for i, ln in enumerate(lines):
            if ln.strip() != "":
                count += 1
                if count >= 2:
                    start_idx = i + 1
                    break

    content_lines = lines[start_idx:]
    while content_lines and content_lines[0].strip() == "":
        content_lines = content_lines[1:]

    content = "\n".join(content_lines).strip()

    if not title:
        title = os.path.splitext(os.path.basename(path))[0]
    if not author:
        author = ""

    return title, author, content


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
):
    """Main video generation pipeline reading `.md` files from `input_dir`.

    Optimized for TikTok with vertical 9:16 format, high-quality TTS,
    and professional visual effects.

    Each `.md` must have a title and author in the first lines as:
    Titulo: My Title
    Autor: Ada

    Then the poem content from the next line onward.
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

        lines = split_text_into_lines(text)
        fragments = []
        subtitles = []
        start_time = 0.0

        # Prepare batch synthesis: collect all non-empty lines and their paths
        texts_to_synthesize = []
        paths_to_synthesize = []
        line_indices = []  # Keep track of which lines are text (not silence)

        for j, line in enumerate(lines):
            frag_path = os.path.join(audio_frag_dir, f"frag_{j + 1}.wav")
            if line.strip() == "":
                # Mark as silence (will be handled separately)
                line_indices.append((j, None, frag_path))
            else:
                texts_to_synthesize.append(line)
                paths_to_synthesize.append(frag_path)
                line_indices.append((j, len(texts_to_synthesize) - 1, frag_path))

        # Generate all audios in a single batch for consistent voice
        if texts_to_synthesize:
            LOGGER.info(
                f"Synthesizing {len(texts_to_synthesize)} text segments in batch..."
            )
            LOGGER.info(f"Text segments: {texts_to_synthesize}")
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

        # Process all segments in order (silences and synthesized texts)
        LOGGER.info(f"Processing {len(line_indices)} segments...")
        for j, text_idx, frag_path in line_indices:
            line = lines[j]
            LOGGER.info(
                f"Processing segment {j}: text_idx={text_idx}, path={frag_path}"
            )

            if line.strip() == "":
                # Silence segment
                write_silence_wav(frag_path, duration=0.5)
                clip = AudioFileClip(frag_path)
                dur = clip.duration
                LOGGER.info(f"Silence {j}: duration={dur:.2f}s")
                # Use subclip to ensure moviepy respects the exact duration
                clip = clip.subclipped(0, dur)
                fragments.append(clip)
                subtitles.append({"text": "", "start": start_time, "duration": dur})
                start_time += dur
            else:
                # Text segment (already synthesized)
                if not os.path.exists(frag_path):
                    LOGGER.error(f"Audio file missing: {frag_path}")
                    continue
                file_size = os.path.getsize(frag_path)
                LOGGER.info(f"Text {j}: loading {frag_path} ({file_size} bytes)")
                clip = AudioFileClip(frag_path)
                LOGGER.info(
                    f"Text {j}: loaded, duration={clip.duration:.2f}s, fps={clip.fps}"
                )
                # Keep full audio - do not trim
                dur = clip.duration
                LOGGER.info(
                    f"Text {j}: final duration={dur:.2f}s, line='{line[:30]}...'"
                )
                # Use subclip to ensure moviepy respects the exact duration
                clip = clip.subclipped(0, dur)
                fragments.append(clip)
                subtitles.append({"text": line, "start": start_time, "duration": dur})
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
    args = parser.parse_args()
    main(args.input_dir, args.out, args.image)
