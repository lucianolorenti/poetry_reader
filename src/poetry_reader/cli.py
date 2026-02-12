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

    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    tts.synthesize_to_file(text, str(out))

    typer.echo(f"WAV generado: {out}")


@app.command("process-drive")
def process_drive(
    drive_config: Path = typer.Option(
        Path("config/drive_config.yaml"),
        "--drive-config",
        help="Path to Google Drive configuration YAML",
    ),
    video_config: Path = typer.Option(
        Path("config/video_defaults.yaml"),
        "--video-config",
        help="Path to video generation defaults YAML",
    ),
    limit: Optional[int] = typer.Option(
        None, "--limit", help="Limit number of videos to process"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Simulate execution without processing"
    ),
):
    """
    Process markdowns from Google Drive according to Excel tracker.

    This command automates the entire workflow:
    1. Authenticates with Google Drive
    2. Downloads Excel tracker
    3. Identifies pending markdowns (where Hecho=False)
    4. Generates videos for each pending markdown
    5. Uploads videos to Google Drive
    6. Updates Excel tracker with results
    7. Uploads updated tracker back to Drive

    Requirements:
    - client_secrets.json in ./credentials/ (from Google Cloud Console)
    - Configured IDs in drive_config.yaml
    - Excel tracker with columns: Autor, Titulo, Texto, Hecho

    Example:
        poetry-reader process-drive
        poetry-reader process-drive --limit 5 --dry-run
    """
    import yaml
    from .drive import authenticate, DriveManager, ExcelTracker
    from .orchestrator import VideoOrchestrator

    if not drive_config.exists():
        typer.echo(f"Error: Drive config not found: {drive_config}", err=True)
        typer.echo(
            "Create it with: cp config/drive_config.yaml.example config/drive_config.yaml"
        )
        raise typer.Exit(1)

    if not video_config.exists():
        typer.echo(f"Error: Video config not found: {video_config}", err=True)
        typer.echo(
            "Create it with: cp config/video_defaults.yaml.example config/video_defaults.yaml"
        )
        raise typer.Exit(1)

    typer.echo("[poetry-reader] Loading configurations...")
    with open(drive_config) as f:
        drive_cfg = yaml.safe_load(f)

    with open(video_config) as f:
        video_cfg = yaml.safe_load(f)

    config = {**drive_cfg, **video_cfg}

    try:
        typer.echo("[poetry-reader] Authenticating with Google Drive...")

        drive = authenticate(
            credentials_path=drive_cfg["google_drive"]["credentials_file"],
            client_secrets_path=drive_cfg["google_drive"]["client_secrets"],
            settings_file=drive_cfg["google_drive"].get("settings_file"),
        )

        drive_manager = DriveManager(
            drive,
            max_retries=drive_cfg["processing"]["max_retries"],
            retry_delay=drive_cfg["processing"]["retry_delay_seconds"],
        )

        excel_tracker_id = drive_cfg["drive"]["excel_tracker_id"]
        if excel_tracker_id == "YOUR_EXCEL_FILE_ID_HERE":
            typer.echo(
                "\nError: Please configure excel_tracker_id in drive_config.yaml",
                err=True,
            )
            typer.echo("Get the ID from your Google Drive file URL")
            raise typer.Exit(1)

        typer.echo(f"[poetry-reader] Downloading Excel tracker...")
        local_excel_path = Path(drive_cfg["local"]["cache_dir"]) / "tracker.xlsx"
        local_excel_path.parent.mkdir(parents=True, exist_ok=True)

        drive_manager.download_file(excel_tracker_id, str(local_excel_path))

        tracker = ExcelTracker(str(local_excel_path))
        tracker.load()

        orchestrator = VideoOrchestrator(drive_manager, tracker, config)

        report = orchestrator.process_all(limit=limit, dry_run=dry_run)

        if report.failed > 0:
            raise typer.Exit(1)

    except KeyboardInterrupt:
        typer.echo("\n[poetry-reader] Interrupted by user")
        raise typer.Exit(130)
    except Exception as e:
        typer.echo(f"\n[poetry-reader] Error: {e}", err=True)
        raise typer.Exit(1)


def main():
    """Entry point for console script"""
    app()


if __name__ == "__main__":
    main()
