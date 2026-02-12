import os
import logging
from typing import Optional
import torch

LOGGER = logging.getLogger(__name__)


class Qwen3TTSWrapper:
    """Wrapper for Qwen3-TTS VoiceDesign - Alibaba's high-quality TTS model.

    Qwen3-TTS VoiceDesign allows creating custom voices through natural language
    descriptions. Supports multiple languages including Spanish and English.

    Installation: pip install qwen-tts
    """

    LANG_MAP = {
        "es": "Spanish",
        "en": "English",
    }

    def __init__(
        self,
        lang: str = "es",
        device: str = "auto",
        model_name: str = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
        default_instruct: Optional[str] = None,
    ):
        """Initialize Qwen3-TTS VoiceDesign.

        Args:
            lang: Language code (es, en, etc.)
            device: Device to use ('auto', 'cpu', 'cuda', 'cuda:0', etc.)
            model_name: Qwen3-TTS model to use (VoiceDesign for voice design)
            default_instruct: Default voice instruction/description
        """
        self.lang = lang.lower()
        self.device = device
        self.model = None
        self.sr = 24000
        self.model_name = model_name
        self.default_instruct = default_instruct or (
            "Voz de hombre maduro, con un registro muy grave y profundo. "
            "El tono es extremadamente tranquilo, sereno y reconfortante. "
            "Habla de forma pausada, con mucha autoridad suave y una resonancia baja."
        )

        self.qwen_lang = self.LANG_MAP.get(self.lang, "Spanish")

        try:
            LOGGER.info(f"Loading Qwen3-TTS model: {model_name}")
            from qwen_tts import Qwen3TTSModel

            if device == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"

            self.model = Qwen3TTSModel.from_pretrained(
                model_name,
                device_map=device,
                dtype=torch.bfloat16 if device.startswith("cuda") else torch.float32,
                attn_implementation="eager",
            )
            LOGGER.info(f"Qwen3-TTS loaded successfully on {device}")
        except ImportError:
            LOGGER.error("Qwen3-TTS not installed. Run: pip install qwen-tts")
            raise
        except Exception as exc:
            LOGGER.exception("Failed to load Qwen3-TTS: %s", exc)
            raise

    def synthesize_to_file(
        self,
        text: str,
        out_path: str,
        instruct: Optional[str] = None,
    ):
        """Generate audio for text and save to file using VoiceDesign.

        Args:
            text: Text to synthesize
            out_path: Output audio file path
            instruct: Voice instruction/description (uses default if not provided)
        """
        import soundfile as sf

        os.makedirs(
            os.path.dirname(out_path) if os.path.dirname(out_path) else ".",
            exist_ok=True,
        )

        try:
            LOGGER.info(f"Generating audio for: {text[:50]}...")

            voice_instruct = instruct if instruct else self.default_instruct

            wavs, sr = self.model.generate_voice_design(
                text=text,
                language=self.qwen_lang,
                instruct=voice_instruct,
            )

            sf.write(out_path, wavs[0], sr)
            LOGGER.info(f"Audio saved to {out_path}")

        except Exception as exc:
            LOGGER.exception("Failed to synthesize with Qwen3-TTS: %s", exc)
            raise


def get_tts(
    backend: str = "qwen3",
    lang: Optional[str] = None,
    model_name: Optional[str] = None,
    voice: Optional[str] = None,
    instruct: Optional[str] = None,
):
    """Factory: return a TTS object with `synthesize_to_file(text, out_path)`.

    Args:
        backend: TTS backend (only 'qwen3' is supported)
        lang: Language code (es, en)
        model_name: Specific Qwen3-TTS model name
        voice: Not used for VoiceDesign (kept for compatibility)
        instruct: Default voice instruction/description

    Returns:
        Qwen3TTSWrapper instance
    """
    lang_code = (lang or "es").lower()

    return Qwen3TTSWrapper(
        lang=lang_code,
        model_name=model_name or "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
        default_instruct=instruct,
    )
