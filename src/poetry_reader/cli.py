import typer
from pathlib import Path
from typing import Optional
from .generate_videos import main as generate_main
import os

app = typer.Typer(help="Poetry Reader CLI")


@app.command()
def generate(
    input_dir: Path = typer.Argument(
        ..., help="Directorio de entrada con archivos .md"
    ),
    out: Path = typer.Option(Path("output"), help="Directorio de salida"),
    image: Path = typer.Option(None, help="Imagen de fondo para los videos"),
    palette: Optional[str] = typer.Option(
        None,
        help="Paleta de colores del gradiente: sunset, ocean, forest, lavender, rose, golden, midnight, peach, mint, autumn (aleatorio si no se especifica)",
    ),
    no_particles: bool = typer.Option(
        False, "--no-particles", help="Desactivar overlay de partículas flotantes"
    ),
    font_size: int = typer.Option(80, help="Tamaño de fuente para el texto en puntos"),
    fade_duration: float = typer.Option(
        0.5, help="Duración del efecto fade in/out en segundos"
    ),
    lang: Optional[str] = typer.Option(
        None,
        help="Forzar idioma para TTS (es=español, en=inglés). Si no se especifica, se detecta automáticamente",
    ),
    fps: int = typer.Option(
        30, help="Frames por segundo del video (30 recomendado para TikTok)"
    ),
    num_particles: int = typer.Option(
        80, help="Número de partículas en el overlay (si está activado)"
    ),
    tts_instruct: Optional[str] = typer.Option(
        None,
        help="Instrucción de voz para Qwen3-TTS VoiceDesign (descripción de la voz deseada)",
    ),
    tts_model: Optional[str] = typer.Option(
        "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
        help="Modelo Qwen3-TTS (default: Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign)",
    ),
    vertical: bool = typer.Option(
        True,
        "--vertical/--horizontal",
        help="Formato vertical 9:16 para TikTok (por defecto)",
    ),
    no_zoom: bool = typer.Option(
        False, "--no-zoom", help="Desactivar efecto de zoom en el fondo"
    ),
):
    """Genera audios y videos desde archivos markdown, optimizado para TikTok"""
    # TikTok vertical resolution (9:16)
    resolution = (1080, 1920) if vertical else (1280, 720)

    generate_main(
        input_dir=str(input_dir),
        out_dir=str(out),
        image_path=str(image) if image else None,
        gradient_palette=palette,
        add_particles=not no_particles,
        font_size=font_size,
        fade_duration=fade_duration,
        force_lang=lang,
        fps=fps,
        num_particles=num_particles,
        tts_backend="qwen3",
        tts_model=tts_model,
        tts_instruct=tts_instruct,
        resolution=resolution,
        tiktok_mode=True,
        zoom_background=not no_zoom,
    )


@app.command("tts-generate")
def tts_generate(
    text: str = typer.Option(..., help="Texto a sintetizar"),
    instruct: Optional[str] = typer.Option(
        None,
        help="Instrucción/detalle de voz (ej: 'Voz grave y pausada de narrador de documentales')",
    ),
    model: Optional[str] = typer.Option(
        "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
        help="Modelo Qwen3-TTS (default: Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign)",
    ),
    device: Optional[str] = typer.Option(
        "auto", help="Device para el modelo ('auto', 'cpu', 'cuda')"
    ),
    lang: Optional[str] = typer.Option("es", help="Idioma (es=español, en=inglés)"),
    out: Path = typer.Option(Path("./out.wav"), help="Ruta de salida para el WAV"),
):
    """Genera un archivo WAV a partir de `text` usando Qwen3-TTS VoiceDesign."""
    from .ttsgenerator import Qwen3TTSWrapper

    tts = Qwen3TTSWrapper(
        lang=lang or "es",
        device=device or "auto",
        model_name=model or "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
        default_instruct=instruct,
    )

    # Aseguramos que el directorio exista
    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    # Synth to file
    tts.synthesize_to_file(text, str(out))

    typer.echo(f"WAV generado: {out}")


def main():
    """Entry point for console script"""
    app()


if __name__ == "__main__":
    main()
