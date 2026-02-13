import os
import logging
from typing import Optional, List, Any
from pathlib import Path
import torch

LOGGER = logging.getLogger(__name__)


class Qwen3TTSWrapper:
    """Wrapper for Qwen3-TTS Base model with voice cloning from reference audio.

    REQUIRES a pre-generated reference audio file. This is mandatory for consistent
    voice cloning across all generations.

    To generate the reference audio:
        poetry-reader generate-voice-reference \
            --instruct "Your voice description" \
            --out assets/voice_reference.wav

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
        reference_wav_path: Optional[str] = None,
        model_name: str = "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
    ):
        """Initialize Qwen3-TTS Base model for voice cloning.

        Args:
            lang: Language code (es, en, etc.)
            device: Device to use ('auto', 'cpu', 'cuda', 'cuda:0', etc.)
            reference_wav_path: Path to reference WAV file (REQUIRED)
            model_name: Qwen3-TTS model to use (should be Base model)

        Raises:
            ValueError: If reference_wav_path is not provided or file doesn't exist
        """
        self.lang = lang.lower()
        self.device = device
        self.model = None
        self.sr = 24000
        self.model_name = model_name
        self.reference_wav_path = reference_wav_path

        # Validate reference_wav_path is provided
        if not reference_wav_path:
            raise ValueError(
                "reference_wav_path is required. "
                "Generate a reference audio first with:\n"
                "  poetry-reader generate-voice-reference "
                "--instruct 'Your voice description' --out assets/voice_reference.wav"
            )

        # Validate file exists
        ref_path = Path(reference_wav_path)
        if not ref_path.exists():
            raise ValueError(
                f"Reference audio file not found: {reference_wav_path}\n"
                "Generate it first with:\n"
                "  poetry-reader generate-voice-reference "
                "--instruct 'Your voice description' "
                f"--out {reference_wav_path}"
            )

        self.qwen_lang = self.LANG_MAP.get(self.lang, "Spanish")
        self._voice_clone_prompt: Optional[Any] = None

        try:
            LOGGER.info(f"Loading Qwen3-TTS Base model on {device}")
            LOGGER.info(f"Reference WAV path: {reference_wav_path}")
            from qwen_tts import Qwen3TTSModel

            if device == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"
            self.device = device
            LOGGER.info(f"Using device: {device}")

            # Load only the Base model for voice cloning
            # For CUDA, use bfloat16 to reduce VRAM usage (half precision)
            self.model = Qwen3TTSModel.from_pretrained(
                model_name,
                device_map=device,
                dtype=torch.bfloat16,
                attn_implementation="eager",
            )

            LOGGER.info(f"Qwen3-TTS Base model loaded successfully on {device}")

            # Create voice clone prompt from reference audio
            self._create_voice_prompt_from_file(str(ref_path))

        except ImportError:
            LOGGER.error("Qwen3-TTS not installed. Run: pip install qwen-tts")
            raise
        except Exception as exc:
            LOGGER.exception("Failed to load Qwen3-TTS: %s", exc)
            raise

    def _create_voice_prompt_from_file(self, wav_path: str) -> None:
        """Create voice clone prompt from reference audio file.

        Args:
            wav_path: Path to reference WAV file
        """
        import soundfile as sf
        import numpy as np

        LOGGER.info(f"Creating voice clone prompt from: {wav_path}")

        # Load reference audio
        ref_audio, ref_sr = sf.read(wav_path)

        # Convert to mono if stereo (shape: [samples, channels] -> [samples])
        if len(ref_audio.shape) > 1:
            ref_audio = np.mean(ref_audio, axis=1)

        # Ensure float32 format
        ref_audio = ref_audio.astype(np.float32)

        # Create voice clone prompt
        ref_text = "Esta es una voz de referencia para lectura de poesía."
        self._voice_clone_prompt = self.model.create_voice_clone_prompt(
            ref_audio=(ref_audio, ref_sr),
            ref_text=ref_text,
        )

        LOGGER.info("Voice clone prompt created successfully from reference file")

    def synthesize_to_file(self, text: str, out_path: str):
        """Generate audio for a single text and save to file.

        Args:
            text: Text to synthesize
            out_path: Output audio file path
        """
        self.synthesize_batch_to_files(
            texts=[text],
            out_paths=[out_path],
        )

    def synthesize_batch_to_files(self, texts: List[str], out_paths: List[str]):
        """Generate audio for multiple texts with consistent voice using voice cloning.

        This method ensures all texts are synthesized with the exact same voice
        by using a cached voice clone prompt from the reference audio.

        Args:
            texts: List of texts to synthesize
            out_paths: List of output audio file paths (must match texts length)
        """
        import soundfile as sf

        if len(texts) != len(out_paths):
            raise ValueError(
                f"Number of texts ({len(texts)}) must match number of out_paths ({len(out_paths)})"
            )

        if not texts:
            LOGGER.warning("No texts provided for synthesis")
            return

        if self._voice_clone_prompt is None:
            raise RuntimeError(
                "No voice clone prompt available. This should not happen - "
                "the prompt should have been created during initialization."
            )

        # Create output directories
        for out_path in out_paths:
            dir_path = os.path.dirname(out_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)

        try:
            LOGGER.info(f"Generating {len(texts)} audio(s) with voice cloning...")

            # Use voice clone with cached prompt for consistent voice
            wavs, sr = self.model.generate_voice_clone(
                text=texts,
                language=[self.qwen_lang] * len(texts),
                voice_clone_prompt=self._voice_clone_prompt,
            )

            # Save each audio to its respective file
            for i, out_path in enumerate(out_paths):
                audio_data = wavs[i]
                LOGGER.info(
                    f"Audio {i + 1}/{len(texts)}: shape={audio_data.shape}, "
                    f"duration={len(audio_data) / sr:.2f}s, sr={sr}"
                )
                sf.write(out_path, audio_data, sr)
                LOGGER.info(f"Audio {i + 1}/{len(texts)} saved to {out_path}")

            LOGGER.info(f"Successfully generated {len(texts)} audio file(s)")

        except Exception as exc:
            LOGGER.exception("Failed to synthesize with Qwen3-TTS: %s", exc)
            raise


def generate_voice_reference(
    instruct: str,
    output_path: str,
    lang: str = "es",
    device: str = "auto",
    ref_text: str = "Esta es una voz de referencia para lectura de poesía.",
):
    """Generate a reference voice audio using VoiceDesign model.

    This function generates a reference audio file that can be used with
    Qwen3TTSWrapper for consistent voice cloning.

    Args:
        instruct: Voice instruction/description (e.g., "Voz grave y pausada...")
        output_path: Path where to save the reference WAV file
        lang: Language code (es, en, etc.)
        device: Device to use ('auto', 'cpu', 'cuda')
        ref_text: Text to use for the reference audio

    Returns:
        str: Path to the generated reference file
    """
    import soundfile as sf

    LOGGER.info(f"Generating voice reference with instruction: {instruct[:50]}...")

    try:
        from qwen_tts import Qwen3TTSModel

        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"

        # Load VoiceDesign model
        LOGGER.info("Loading VoiceDesign model...")
        design_model = Qwen3TTSModel.from_pretrained(
            "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
            device_map=device,
            dtype=torch.bfloat16 if device.startswith("cuda") else torch.float32,
            attn_implementation="eager",
        )

        # Map language
        lang_map = {"es": "Spanish", "en": "English"}
        qwen_lang = lang_map.get(lang.lower(), "Spanish")

        # Generate reference audio
        LOGGER.info("Generating reference audio...")
        ref_wavs, ref_sr = design_model.generate_voice_design(
            text=ref_text,
            language=qwen_lang,
            instruct=instruct,
        )

        # Convert to mono if needed (ensure shape is [samples])
        ref_audio = ref_wavs[0]
        if len(ref_audio.shape) > 1:
            import numpy as np

            ref_audio = np.mean(ref_audio, axis=1).astype(np.float32)

        # Save reference audio
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        sf.write(output_path, ref_audio, ref_sr)

        LOGGER.info(f"Voice reference saved to: {output_path}")
        return output_path

    except ImportError:
        LOGGER.error("Qwen3-TTS not installed. Run: pip install qwen-tts")
        raise
    except Exception as exc:
        LOGGER.exception("Failed to generate voice reference: %s", exc)
        raise


def get_tts(
    backend: str = "qwen3",
    lang: Optional[str] = None,
    model_name: Optional[str] = None,
    reference_wav_path: Optional[str] = None,
    device: str = "auto",
    model_size: str = "1.7B",
):
    """Factory: return a TTS object with `synthesize_to_file(text, out_path)`.

    Args:
        backend: TTS backend (only 'qwen3' is supported)
        lang: Language code (es, en)
        model_name: Specific Qwen3-TTS model name (should be Base model)
        reference_wav_path: Path to reference WAV file (REQUIRED)
        device: Device to use ('auto', 'cpu', 'cuda', 'cuda:0', etc.)
        model_size: Model size - "1.7B" or "0.6B" (default: "1.7B")

    Returns:
        Qwen3TTSWrapper instance

    Raises:
        ValueError: If reference_wav_path is not provided or file doesn't exist
    """
    lang_code = (lang or "es").lower()

    # Map model_size to actual model name
    if not model_name:
        if model_size == "0.6B":
            model_name = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
        else:
            model_name = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"

    return Qwen3TTSWrapper(
        lang=lang_code,
        model_name=model_name,
        reference_wav_path=reference_wav_path,
        device=device,
    )
