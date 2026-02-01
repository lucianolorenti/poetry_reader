import os
import logging
from typing import Optional
from TTS.api import TTS


LOGGER = logging.getLogger(__name__)

# Map languages to Coqui TTS model names. Using VITS models for better quality.
# VITS provides more natural sounding voices compared to Tacotron2.
MODEL_BY_LANG = {
    "es": "tts_models/es/css10/vits",  # Better Spanish VITS model
    "en": "tts_models/en/ljspeech/vits",  # Better English VITS model
}
DEFAULT_MODEL = "tts_models/en/ljspeech/vits"


class CoquiTTS:
    def __init__(self, model_name: Optional[str] = None, lang: Optional[str] = None):
        """Create a Coqui TTS wrapper.

        You can pass either `model_name` explicitly, or `lang` (e.g. "es", "en")
        and the class will select a model from `MODEL_BY_LANG`. If model loading
        fails the code will fall back to `DEFAULT_MODEL`.
        """
        if model_name is None:
            if lang and lang in MODEL_BY_LANG:
                model_name = MODEL_BY_LANG[lang]
            else:
                model_name = DEFAULT_MODEL

        self.model_name = model_name
        self.tts = None
        try:
            LOGGER.info(f"Loading TTS model: %s", model_name)
            self.tts = TTS(model_name)
        except Exception as exc:  # pragma: no cover - runtime fallback
            LOGGER.exception("Failed to load TTS model %s: %s", model_name, exc)
            if model_name != DEFAULT_MODEL:
                try:
                    LOGGER.info("Falling back to default model: %s", DEFAULT_MODEL)
                    self.tts = TTS(DEFAULT_MODEL)
                    self.model_name = DEFAULT_MODEL
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

    def __init__(self, lang: str = "ES", device: str = "auto"):
        """Initialize MeloTTS.

        Args:
            lang: Language code (ES for Spanish, EN for English, etc.)
            device: Device to use ('auto', 'cpu', 'cuda')
        """
        self.lang = lang.upper()
        self.device = device
        self.model = None
        self.sr = 44100

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
        speaker_id: int = 0,
        speed: float = 1.0,
    ):
        """Generate audio for text and save to file.

        Args:
            text: Text to synthesize
            out_path: Output audio file path
            speaker_id: Speaker ID (0 is default, varies by language)
            speed: Speaking speed (1.0 is normal)
        """
        import torchaudio as ta
        import torch
        import numpy as np

        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        try:
            # Generate audio
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
            LOGGER.info(f"Audio saved to {out_path}")

        except Exception as exc:
            LOGGER.exception("Failed to synthesize with MeloTTS: %s", exc)
            raise


def get_tts(
    backend: str = "melo", lang: Optional[str] = None, model_name: Optional[str] = None
):
    """Factory: return a TTS object with `synthesize_to_file(text, out_path)`.

    Backends:
    - 'melo': MeloTTS (recommended for Spanish, high quality, free)
    - 'coqui': Coqui TTS (open source, good quality)
    - 'chatterbox': Chatterbox TTS (multilingual)
    """
    b = (backend or "melo").lower()
    lang_code = (lang or "es").lower()

    if b == "melo":
        # MeloTTS uses 2-letter codes
        melo_lang = "ES" if lang_code.startswith("es") else "EN"
        return MeloTTSWrapper(lang=melo_lang)
    elif b == "coqui":
        return CoquiTTS(model_name=model_name, lang=lang_code)
    elif b == "chatterbox":
        return ChatterboxTTS(lang=lang_code, model_name=model_name)
    else:
        raise ValueError("Unknown TTS backend: %s" % backend)
