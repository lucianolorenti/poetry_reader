import os
import logging
from typing import Optional


LOGGER = logging.getLogger(__name__)


class CoquiTTS:
    """Coqui TTS wrapper (optional dependency).

    Install with: pip install TTS
    """

    # Map languages to Coqui TTS model names. Using VITS models for better quality.
    # VITS provides more natural sounding voices compared to Tacotron2.
    MODEL_BY_LANG = {
        "es": "tts_models/es/css10/vits",  # Better Spanish VITS model
        "en": "tts_models/en/ljspeech/vits",  # Better English VITS model
    }
    DEFAULT_MODEL = "tts_models/en/ljspeech/vits"

    def __init__(self, model_name: Optional[str] = None, lang: Optional[str] = None):
        """Create a Coqui TTS wrapper.

        You can pass either `model_name` explicitly, or `lang` (e.g. "es", "en")
        and the class will select a model from `MODEL_BY_LANG`. If model loading
        fails the code will fall back to `DEFAULT_MODEL`.
        """
        from TTS.api import TTS

        if model_name is None:
            if lang and lang in self.MODEL_BY_LANG:
                model_name = self.MODEL_BY_LANG[lang]
            else:
                model_name = self.DEFAULT_MODEL

        self.model_name = model_name
        self.tts = None
        try:
            LOGGER.info(f"Loading TTS model: %s", model_name)
            self.tts = TTS(model_name)
        except Exception as exc:  # pragma: no cover - runtime fallback
            LOGGER.exception("Failed to load TTS model %s: %s", model_name, exc)
            if model_name != self.DEFAULT_MODEL:
                try:
                    LOGGER.info("Falling back to default model: %s", self.DEFAULT_MODEL)
                    self.tts = TTS(self.DEFAULT_MODEL)
                    self.model_name = self.DEFAULT_MODEL
                except Exception:
                    LOGGER.exception("Failed to load default TTS model")
                    raise

    def synthesize_to_file(self, text: str, out_path: str):
        """Generate a WAV file at `out_path` from `text`.

        Ensures parent directories exist.
        """
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        # Use the high-level API if available
        if hasattr(self.tts, "tts_to_file"):
            self.tts.tts_to_file(text=text, file_path=out_path)
        else:
            # Fallback for older/newer APIs
            self.tts.tts_to_file(text, out_path)


class ChatterboxTTS:
    """Simple adapter that uses the official `chatterbox-tts` classes directly.

    This implementation deliberately avoids probing many different API shapes
    and instead imports the recommended classes `chatterbox.tts.ChatterboxTTS`
    and `chatterbox.mtl_tts.ChatterboxMultilingualTTS` directly. If the package
    is not installed the import error will propagate so the caller is aware.
    """

    def __init__(
        self,
        lang: Optional[str] = None,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
    ):
        """Initialize a Chatterbox-backed TTS.

        - If `model_name` contains "mtl" the multilingual class is used.
        - `device` is passed to `from_pretrained()` as in the upstream example.
        """
        self.is_multilingual = False
        device = device or "cpu"
        if model_name and "mtl" in model_name.lower():
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS as CB_MTL  # type: ignore

            self.model = CB_MTL.from_pretrained(device=device)
            self.is_multilingual = True
        else:
            from chatterbox.tts import ChatterboxTTS as CB_TTS  # type: ignore

            self.model = CB_TTS.from_pretrained(device=device)

        # sample rate attribute on chatterbox models is `sr` in the example
        self.sr = getattr(self.model, "sr", 24000)
        self.lang = lang

    def synthesize_to_file(
        self,
        text: str,
        out_path: str,
        audio_prompt_path: Optional[str] = None,
    ):
        """Generate audio for `text` and write WAV to `out_path`.

        This mirrors the example from the chatterbox repository and uses
        `torchaudio.save` to write the result. Errors from missing deps or
        unexpected tensor shapes are allowed to propagate.
        """
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        # Call generate; multilingual models often expect `language_id`
        if self.is_multilingual and self.lang is not None:
            wav = self.model.generate(text, language_id=self.lang)
        else:
            # Pass audio prompt if provided — upstream supports this in examples
            if audio_prompt_path:
                try:
                    wav = self.model.generate(text, audio_prompt_path=audio_prompt_path)
                except TypeError:
                    # Some versions may not accept audio_prompt_path; fall back
                    wav = self.model.generate(text)
            else:
                wav = self.model.generate(text)

        # Normalize output to a numpy/torch tensor and save with torchaudio
        import torchaudio as ta  # type: ignore
        import torch
        import numpy as np

        if isinstance(wav, (list, tuple)):
            wav_arr = wav[0]
        else:
            wav_arr = wav

        if isinstance(wav_arr, torch.Tensor):
            tensor = wav_arr
        else:
            tensor = torch.from_numpy(np.array(wav_arr))

        # Ensure shape is [channels, time]
        if tensor.ndim == 1:
            tensor = tensor.unsqueeze(0)
        elif tensor.ndim == 2 and tensor.shape[0] > tensor.shape[1]:
            tensor = tensor.T

        ta.save(out_path, tensor, int(self.sr))


class MeloTTSWrapper:
    """Wrapper for MeloTTS - high quality multilingual TTS, excellent for Spanish.

    MeloTTS provides very natural sounding voices and supports Spanish with
    high quality. It runs in real-time on CPU.

    Installation: pip install melotts
    """

    def __init__(
        self, lang: str = "ES", voice: Optional[str] = None, device: str = "auto"
    ):
        """Initialize MeloTTS.

        Args:
            lang: Language code (ES for Spanish, EN for English, etc.)
            voice: Optional voice name or speaker ID
            device: Device to use ('auto', 'cpu', 'cuda')
        """
        self.lang = lang.upper()
        self.device = device
        self.model = None
        self.sr = 44100

        # Determine speaker_id from voice
        self.speaker_id = 0
        if voice is not None:
            try:
                self.speaker_id = int(voice)
            except (ValueError, TypeError):
                # Default to 0 if voice is not a valid integer
                self.speaker_id = 0

        try:
            from melo.api import TTS as MeloTTS

            LOGGER.info(f"Loading MeloTTS model for language: {self.lang}")
            self.model = MeloTTS(language=self.lang, device=device)
            LOGGER.info("MeloTTS loaded successfully")
        except ImportError:
            LOGGER.error("MeloTTS not installed. Run: pip install melotts")
            raise
        except Exception as exc:
            LOGGER.exception("Failed to load MeloTTS: %s", exc)
            raise

    def synthesize_to_file(
        self,
        text: str,
        out_path: str,
        speaker_id: Optional[int] = None,
        speed: float = 1.0,
    ):
        """Generate audio for text and save to file.

        Args:
            text: Text to synthesize
            out_path: Output audio file path
            speaker_id: Speaker ID (if None, uses self.speaker_id)
            speed: Speaking speed (1.0 is normal)
        """
        import torchaudio as ta
        import torch
        import numpy as np

        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        # Use the speaker_id passed in, or the one from initialization if None or 0 (default)
        if speaker_id is None or speaker_id == 0:
            speaker_id = self.speaker_id

        try:
            if hasattr(self.model, "tts_to_file"):
                self.model.tts_to_file(
                    text,
                    speaker_id=speaker_id,
                    output_path=out_path,
                    speed=speed,
                )
                LOGGER.info("Audio saved to %s", out_path)
                return

            # Generate audio (legacy API)
            wav = self.model.synthesize(
                text,
                speaker_id=speaker_id,
                speed=speed,
            )

            # Convert to tensor and save
            if isinstance(wav, np.ndarray):
                tensor = torch.from_numpy(wav)
            elif isinstance(wav, torch.Tensor):
                tensor = wav
            else:
                tensor = torch.tensor(wav)

            # Ensure shape is [channels, time]
            if tensor.ndim == 1:
                tensor = tensor.unsqueeze(0)
            elif tensor.ndim == 2 and tensor.shape[0] > tensor.shape[1]:
                tensor = tensor.T

            ta.save(out_path, tensor, self.sr)
            LOGGER.info("Audio saved to %s", out_path)

        except Exception as exc:
            LOGGER.exception("Failed to synthesize with MeloTTS: %s", exc)
            raise


class KokoroTTSWrapper:
    """Wrapper for Kokoro TTS - lightweight, fast, high-quality TTS.

    Kokoro is an efficient TTS model that runs locally with high quality voices.
    Supports multiple languages and voices.

    Installation: pip install kokoro
    """

    # Voice mappings for different languages.
    # For Spanish, native Kokoro voices include (per VOICES.md):
    # - Male: 'em_alex', 'em_santa'
    # - Female: 'ef_dora'
    VOICES_BY_LANG = {
        "es": "em_alex",  # Native Spanish voice (male)
        "en": "af_bella",  # American English (female)
        "en-us": "af_bella",  # American English
        "en-gb": "bf_alice",  # British English
        "fr": "ff_siwis",  # French
        "it": "if_sara",  # Italian
    }
    VOICE_ALIASES = {
        # Legacy Spanish names used before Kokoro renamed voices
        "es_alex": "em_alex",
        "es_david": "em_santa",
        "es_fernando": "em_santa",
        "es_belen": "ef_dora",
        "es_estela": "ef_dora",
    }
    DEFAULT_VOICE = "af_bella"

    def __init__(
        self, lang: str = "es", voice: Optional[str] = None, device: str = "cpu"
    ):
        """Initialize Kokoro TTS.

        Args:
            lang: Language code (es, en, etc.)
            voice: Specific voice to use (overrides lang selection).
                   Can be any valid Kokoro voice name (e.g., 'af_bella', 'em_alex').
            device: Device to use ('cpu', 'cuda', etc.)
        """
        self.lang = lang.lower()
        self.device = device
        self.model = None
        self.pipeline = None
        self.sr = 24000  # Kokoro uses 24kHz sample rate

        # Select voice based on language if not explicitly provided.
        # This allows passing any voice name directly via the `voice` parameter.
        if voice is None:
            voice = self.VOICES_BY_LANG.get(
                self.lang, self.VOICES_BY_LANG.get(self.lang[:2], self.DEFAULT_VOICE)
            )
        self.voice = self.VOICE_ALIASES.get(voice, voice)

        try:
            LOGGER.info(f"Loading Kokoro TTS with voice: {self.voice}")

            # Try different import patterns
            try:
                from kokoro import KPipeline

                # Kokoro uses single-letter language codes: 'a' (US English), 'b' (UK English),
                # 'e' (Spanish), 'f' (French), etc.
                k_lang = "a"  # Default
                if self.voice and self.voice.startswith("e"):
                    k_lang = "e"
                elif self.voice and (
                    self.voice.startswith("bf_") or self.voice.startswith("bm_")
                ):
                    k_lang = "b"
                elif self.voice and (
                    self.voice.startswith("af_") or self.voice.startswith("am_")
                ):
                    k_lang = "a"
                elif self.lang.startswith("es"):
                    k_lang = "e"
                elif self.lang.startswith("en-gb"):
                    k_lang = "b"
                elif self.voice and "_" in self.voice and len(self.voice) > 2:
                    # Heuristic: first letter of voice prefix often matches lang_code
                    # (except for English which uses 'a'/'b')
                    k_lang = self.voice[0]
                else:
                    # Fallback to first letter of language code
                    k_lang = self.lang[0]

                self.pipeline = KPipeline(lang_code=k_lang)
                LOGGER.info(f"Kokoro KPipeline loaded with lang_code: {k_lang}")
            except ImportError:
                # Fallback to alternative API
                try:
                    import kokoro

                    self.model = kokoro.KokoroTTS()
                    LOGGER.info("KokoroTTS loaded successfully")
                except ImportError:
                    LOGGER.error("Kokoro not installed. Run: pip install kokoro")
                    raise

        except Exception as exc:
            LOGGER.exception("Failed to load Kokoro TTS: %s", exc)
            raise

    def synthesize_to_file(
        self,
        text: str,
        out_path: str,
        speed: float = 1.0,
    ):
        """Generate audio for text and save to file.

        Args:
            text: Text to synthesize
            out_path: Output audio file path
            speed: Speaking speed (1.0 is normal)
        """
        import soundfile as sf
        import numpy as np

        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        try:
            if self.pipeline is not None:
                # Use KPipeline API
                generator = self.pipeline(text, voice=self.voice, speed=speed)
                # Collect all audio chunks
                audio_chunks = []
                for _, _, audio in generator:
                    if isinstance(audio, np.ndarray):
                        audio_chunks.append(audio)
                    else:
                        # Convert tensor to numpy
                        audio_chunks.append(
                            audio.numpy()
                            if hasattr(audio, "numpy")
                            else np.array(audio)
                        )

                if audio_chunks:
                    # Concatenate all chunks
                    full_audio = np.concatenate(audio_chunks, axis=0)
                    # Ensure shape is [samples] or [channels, samples]
                    if (
                        full_audio.ndim == 2
                        and full_audio.shape[0] > full_audio.shape[1]
                    ):
                        full_audio = full_audio.T

                    sf.write(out_path, full_audio, self.sr)
                else:
                    raise RuntimeError("No audio generated")
            elif self.model is not None:
                # Use alternative KokoroTTS API
                audio = self.model.tts(text, voice=self.voice, speed=speed)
                if not isinstance(audio, np.ndarray):
                    audio = (
                        audio.numpy() if hasattr(audio, "numpy") else np.array(audio)
                    )

                sf.write(out_path, audio, self.sr)
            else:
                raise RuntimeError("Kokoro model not initialized")

            LOGGER.info(f"Audio saved to {out_path}")

        except Exception as exc:
            LOGGER.exception("Failed to synthesize with Kokoro TTS: %s", exc)
            raise


def get_tts(
    backend: str = "kokoro",
    lang: Optional[str] = None,
    model_name: Optional[str] = None,
    voice: Optional[str] = None,
):
    """Factory: return a TTS object with `synthesize_to_file(text, out_path)`.

    Backends:
    - 'kokoro': Kokoro TTS (default - fast, lightweight, high quality)
    - 'melo': MeloTTS (recommended for Spanish, high quality, free)
    - 'coqui': Coqui TTS (open source, good quality)
    - 'chatterbox': Chatterbox TTS (multilingual)
    """
    b = (backend or "kokoro").lower()
    lang_code = (lang or "es").lower()

    if b == "kokoro":
        return KokoroTTSWrapper(lang=lang_code, voice=voice)
    elif b == "melo":
        # MeloTTS uses 2-letter codes
        melo_lang = "ES" if lang_code.startswith("es") else "EN"
        return MeloTTSWrapper(lang=melo_lang, voice=voice)
    elif b == "coqui":
        return CoquiTTS(model_name=model_name, lang=lang_code)
    elif b == "chatterbox":
        return ChatterboxTTS(lang=lang_code, model_name=model_name)
    else:
        raise ValueError("Unknown TTS backend: %s" % backend)
