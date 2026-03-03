import typer
from pathlib import Path
from typing import Optional
from .generate_videos import main as generate_main
import logging

# Configure logging to show INFO messages
logging.basicConfig(
    level=logging.INFO,
    format="[%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

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
    tts_model: Optional[str] = typer.Option(
        "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
        help="Modelo Qwen3-TTS (default: Qwen/Qwen3-TTS-12Hz-1.7B-Base para voice cloning)",
    ),
    tts_reference_wav: str = typer.Option(
        ...,  # Required
        help="Ruta al archivo WAV de referencia para voice cloning (REQUIRED). Generate with: generate-voice-reference",
    ),
    device: str = typer.Option(
        "auto",
        help="Device para TTS: 'auto' (default, usa CUDA si disponible), 'cpu', 'cuda', 'cuda:0', etc.",
    ),
    tts_model_size: str = typer.Option(
        "1.7B",
        help="Tamaño del modelo TTS: '1.7B' (calidad alta, ~8GB VRAM) o '0.6B' (más rápido, ~3GB VRAM)",
    ),
    vertical: bool = typer.Option(
        True,
        "--vertical/--horizontal",
        help="Formato vertical 9:16 para TikTok (por defecto)",
    ),
    no_zoom: bool = typer.Option(
        False, "--no-zoom", help="Desactivar efecto de zoom en el fondo"
    ),
    upload: bool = typer.Option(
        False, "--upload", help="Subir videos a Google Drive después de generarlos"
    ),
    drive_config: Path = typer.Option(
        Path("config/drive_config.yaml"),
        "--drive-config",
        help="Path a la configuración de Google Drive (requerido si --upload está activo)",
    ),
):
    """Genera audios y videos desde archivos markdown, optimizado para TikTok"""
    resolution = (1080, 1920) if vertical else (1280, 720)

    # Configurar callback de upload si está activado
    upload_callback = None
    if upload:
        if not drive_config.exists():
            typer.echo(f"Error: Drive config not found: {drive_config}", err=True)
            typer.echo(
                "Create it with: cp config/drive_config.yaml.example config/drive_config.yaml"
            )
            raise typer.Exit(1)

        import yaml
        from .drive import authenticate, DriveManager

        typer.echo("[poetry-reader] Loading Drive configuration for upload...")
        with open(drive_config) as f:
            drive_cfg = yaml.safe_load(f)

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

        videos_folder_id = drive_cfg["drive"]["videos_output_folder_id"]
        if videos_folder_id == "YOUR_VIDEOS_FOLDER_ID_HERE":
            typer.echo(
                "\nError: Please configure videos_output_folder_id in drive_config.yaml",
                err=True,
            )
            raise typer.Exit(1)

        def upload_video_callback(video_info: dict):
            """Callback para subir video a Drive después de generarlo."""
            video_path = video_info["video_path"]
            title = video_info["title"]

            typer.echo(f"  → Uploading to Drive: {title}")

            # Verificar si ya existe y eliminarlo
            from pathlib import Path

            video_file = Path(video_path)
            existing_file = drive_manager.find_file_by_name(
                videos_folder_id, video_file.name
            )
            if existing_file:
                typer.echo(f"  → Replacing existing file: {video_file.name}")
                drive_manager.delete_file(existing_file.id)

            # Subir el video
            video_id = drive_manager.upload_file(
                str(video_file), videos_folder_id, video_file.name
            )
            typer.echo(
                f"  ✓ Video uploaded: https://drive.google.com/file/d/{video_id}"
            )

        upload_callback = upload_video_callback
        typer.echo("[poetry-reader] Upload to Drive enabled\n")

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
        tts_reference_wav=tts_reference_wav,
        device=device,
        tts_model_size=tts_model_size,
        resolution=resolution,
        tiktok_mode=True,
        zoom_background=not no_zoom,
        upload_callback=upload_callback,
    )


@app.command("tts-generate")
def tts_generate(
    text: str = typer.Option(..., help="Texto a sintetizar"),
    reference_wav: str = typer.Option(
        ...,  # Required
        help="Ruta al archivo WAV de referencia para voice cloning",
    ),
    device: Optional[str] = typer.Option(
        "auto", help="Device para el modelo ('auto', 'cpu', 'cuda')"
    ),
    lang: Optional[str] = typer.Option("es", help="Idioma (es=español, en=inglés)"),
    out: Path = typer.Option(Path("./out.wav"), help="Ruta de salida para el WAV"),
):
    """Genera un archivo WAV a partir de `text` usando voice cloning desde referencia."""
    from .ttsgenerator import Qwen3TTSWrapper

    tts = Qwen3TTSWrapper(
        lang=lang or "es",
        device=device or "auto",
        reference_wav_path=reference_wav,
    )

    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    tts.synthesize_to_file(text, str(out))

    typer.echo(f"WAV generado: {out}")


@app.command("generate-voice-reference")
def generate_voice_reference_cmd(
    instruct: str = typer.Option(
        ...,
        help="Descripción de la voz deseada (ej: 'Voz grave y pausada de narrador de poemas')",
    ),
    out: Path = typer.Option(
        Path("assets/voice_reference.wav"),
        help="Ruta de salida para el archivo de referencia",
    ),
    lang: Optional[str] = typer.Option("es", help="Idioma (es=español, en=inglés)"),
    device: Optional[str] = typer.Option(
        "auto", help="Device para el modelo ('auto', 'cpu', 'cuda')"
    ),
):
    """Genera un archivo WAV de referencia para voice cloning consistente.

    Este archivo se usa como referencia para mantener la misma voz
    en todas las generaciones posteriores.

    Ejemplo:
        poetry-reader generate-voice-reference --instruct "Voz grave y pausada"
    """
    from .ttsgenerator import generate_voice_reference

    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        generate_voice_reference(
            instruct=instruct,
            output_path=str(out),
            lang=lang or "es",
            device=device or "auto",
        )
        typer.echo(f"Archivo de referencia generado: {out}")
        typer.echo(
            "Este archivo puede usarse en la configuración de video para mantener consistencia de voz."
        )
    except Exception as e:
        typer.echo(f"Error generando referencia: {e}", err=True)
        raise typer.Exit(1)


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
    no_upload: bool = typer.Option(
        False, "--no-upload", help="Skip uploading videos to Google Drive"
    ),
    upload_youtube: bool = typer.Option(
        False,
        "--upload-youtube",
        help="Also upload videos to YouTube with poem metadata",
    ),
    youtube_privacy: str = typer.Option(
        "private",
        "--youtube-privacy",
        help="YouTube video privacy: private, unlisted, or public",
    ),
):
    """
    Process markdowns from Google Drive according to Excel tracker.

    This command automates the entire workflow:
    1. Authenticates with Google Drive
    2. Downloads Excel tracker
    3. Identifies pending markdowns (where Hecho=False)
    4. Generates videos for each pending markdown
    5. Uploads videos to Google Drive (unless --no-upload)
    6. Optionally uploads to YouTube with poem metadata (--upload-youtube)
    7. Updates Excel tracker with results
    8. Uploads updated tracker back to Drive

    Requirements:
    - client_secrets.json in ./credentials/ (from Google Cloud Console)
    - For YouTube: credentials/youtube_client_secrets.json
    - Configured IDs in drive_config.yaml
    - Excel tracker with columns: Autor, Titulo, Texto, Hecho

    Example:
        poetry-reader process-drive
        poetry-reader process-drive --limit 5 --dry-run
        poetry-reader process-drive --no-upload  # Generate videos but don't upload
        poetry-reader process-drive --upload-youtube  # Also upload to YouTube
        poetry-reader process-drive --upload-youtube --youtube-privacy unlisted
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

        typer.echo("[poetry-reader] Downloading Excel tracker...")
        local_excel_path = Path(drive_cfg["local"]["cache_dir"]) / "tracker.xlsx"
        local_excel_path.parent.mkdir(parents=True, exist_ok=True)

        drive_manager.download_file(excel_tracker_id, str(local_excel_path))

        tracker = ExcelTracker(str(local_excel_path))
        tracker.load()

        orchestrator = VideoOrchestrator(drive_manager, tracker, config)

        upload_to_drive = not no_upload
        if not upload_to_drive:
            typer.echo(
                "[poetry-reader] Upload to Drive disabled (videos will be generated locally only)"
            )

        if upload_youtube:
            typer.echo(
                "[poetry-reader] YouTube upload enabled with privacy: "
                + youtube_privacy
            )
            # Validar privacidad
            if youtube_privacy not in ["private", "unlisted", "public"]:
                typer.echo(
                    "Error: --youtube-privacy must be 'private', 'unlisted', or 'public'",
                    err=True,
                )
                raise typer.Exit(1)

        report = orchestrator.process_all(
            limit=limit,
            dry_run=dry_run,
            upload_to_drive=upload_to_drive,
            upload_to_youtube=upload_youtube,
            youtube_privacy=youtube_privacy,
        )

        report = orchestrator.process_all(
            limit=limit, dry_run=dry_run, upload_to_drive=upload_to_drive
        )

        if report.failed > 0:
            raise typer.Exit(1)

    except KeyboardInterrupt:
        typer.echo("\n[poetry-reader] Interrupted by user")
        raise typer.Exit(130)
    except Exception as e:
        typer.echo(f"\n[poetry-reader] Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def upload(
    video_source: str = typer.Argument(
        ...,
        help="Path al video local o Google Drive file ID (ej: ./output/video.mp4 o 1ABC123...)",
    ),
    markdown: Optional[Path] = typer.Option(
        None,
        "--markdown",
        "-m",
        help="Path al archivo markdown con el poema (para extraer título, autor y texto)",
    ),
    title: Optional[str] = typer.Option(
        None,
        "--title",
        "-t",
        help="Título del video (default: extraído del archivo markdown o del nombre del archivo)",
    ),
    description: Optional[str] = typer.Option(
        None,
        "--description",
        "-d",
        help="Descripción del video (default: extraída del archivo markdown)",
    ),
    tags: Optional[str] = typer.Option(
        None, "--tags", help="Tags separados por coma (ej: 'poetry,poem,spoken word')"
    ),
    privacy: str = typer.Option(
        "private", "--privacy", "-p", help="Privacidad: private, unlisted, o public"
    ),
    category: str = typer.Option(
        "27",
        "--category",
        "-c",
        help="ID de categoría de YouTube (default: 27 - Education)",
    ),
    is_drive_id: bool = typer.Option(
        False,
        "--from-drive",
        help="Interpretar video_source como Google Drive file ID en lugar de path local",
    ),
    drive_config: Path = typer.Option(
        Path("config/drive_config.yaml"),
        "--drive-config",
        help="Path a la configuración de Google Drive (necesario si --from-drive)",
    ),
):
    """
    Sube un video a YouTube.

    El video puede venir de un path local o de Google Drive (especificando --from-drive).

    Si proporcionas un archivo markdown (--markdown), se extraerá automáticamente:
    - Título: "Titulo del poema - Autor"
    - Descripción: "Titulo del poema, Autor\n\n[texto del poema]"

    Examples:
        # Subir video local con metadata del poema
        poetry-reader upload ./output/video.mp4 --markdown ./input/poema.md

        # Subir desde Google Drive
        poetry-reader upload 1ABC123xyz --from-drive --markdown ./poema.md

        # Con opciones personalizadas
        poetry-reader upload ./video.mp4 --markdown ./poema.md --tags "poetry,art" --privacy unlisted
    """
    import tempfile
    import os
    from .youtube import YouTubeUploader

    temp_download_path = None
    video_path = None

    try:
        # Determinar el path del video (local o descargar de Drive)
        if is_drive_id:
            # Descargar de Google Drive
            import yaml
            from .drive import authenticate as drive_auth, DriveManager

            if not drive_config.exists():
                typer.echo(f"Error: Drive config not found: {drive_config}", err=True)
                raise typer.Exit(1)

            with open(drive_config) as f:
                drive_cfg = yaml.safe_load(f)

            typer.echo("[poetry-reader] Authenticating with Google Drive...")
            drive = drive_auth(
                credentials_path=drive_cfg["google_drive"]["credentials_file"],
                client_secrets_path=drive_cfg["google_drive"]["client_secrets"],
                settings_file=drive_cfg["google_drive"].get("settings_file"),
            )

            drive_manager = DriveManager(
                drive,
                max_retries=drive_cfg["processing"]["max_retries"],
                retry_delay=drive_cfg["processing"]["retry_delay_seconds"],
            )

            # Crear archivo temporal para descargar
            temp_dir = tempfile.mkdtemp()
            temp_download_path = os.path.join(temp_dir, "video_to_upload.mp4")

            typer.echo(
                f"[poetry-reader] Downloading video from Drive (ID: {video_source})..."
            )
            success = drive_manager.download_file(video_source, temp_download_path)
            if not success:
                typer.echo("✗ Failed to download video from Drive", err=True)
                raise typer.Exit(1)

            video_path = temp_download_path
            typer.echo(f"✓ Video downloaded to: {video_path}")
        else:
            # Usar path local
            video_path_obj = Path(video_source)
            if not video_path_obj.exists():
                typer.echo(f"Error: Video file not found: {video_source}", err=True)
                raise typer.Exit(1)
            video_path = str(video_path_obj)

        # Configurar metadatos
        video_path_obj = Path(video_path)

        # Extraer información del markdown si está disponible
        poem_data = None
        if markdown:
            if markdown.exists():
                from .utils import parse_markdown_file

                try:
                    poem_data = parse_markdown_file(str(markdown))
                    typer.echo(
                        f"[poetry-reader] Loaded poem: '{poem_data['titulo']}' by {poem_data['autor']}"
                    )
                except Exception as e:
                    typer.echo(f"[WARNING] Failed to parse markdown: {e}", err=True)
            else:
                typer.echo(f"[WARNING] Markdown file not found: {markdown}", err=True)

        # Construir título y descripción
        if poem_data:
            # Usar información del poema
            actual_title = title or f"{poem_data['titulo']} - {poem_data['autor']}"
            if description:
                actual_description = description
            else:
                # Descripción con título, autor y texto del poema
                actual_description = f"{poem_data['titulo']}\n{poem_data['autor']}\n\n{poem_data['texto']}"
        else:
            # Usar valores por defecto o los proporcionados
            actual_title = (
                title or video_path_obj.stem.replace("_", " ").replace("-", " ").title()
            )
            actual_description = (
                description or f"Uploaded via poetry-reader from {video_path_obj.name}"
            )

        tag_list = tags.split(",") if tags else []

        # Validar privacidad
        if privacy not in ["private", "unlisted", "public"]:
            typer.echo(
                f"Error: Privacy must be 'private', 'unlisted', or 'public'", err=True
            )
            raise typer.Exit(1)

        # Subir a YouTube
        typer.echo("[poetry-reader] Initializing YouTube uploader...")
        uploader = YouTubeUploader()

        typer.echo(f"[poetry-reader] Uploading to YouTube: {actual_title}")
        typer.echo(f"  Privacy: {privacy}")
        if tag_list:
            typer.echo(f"  Tags: {', '.join(tag_list)}")

        response = uploader.upload_video(
            video_path=video_path,
            title=actual_title,
            description=actual_description,
            tags=tag_list,
            privacy_status=privacy,
            category_id=category,
        )

        video_id = response.get("id")
        typer.echo(f"\n✓ Upload complete!")
        typer.echo(f"  Video ID: {video_id}")
        typer.echo(f"  URL: https://youtu.be/{video_id}")

    except Exception as e:
        typer.echo(f"\n[poetry-reader] Error: {e}", err=True)
        raise typer.Exit(1)

    finally:
        # Limpiar archivo temporal si se descargó de Drive
        if temp_download_path and os.path.exists(temp_download_path):
            try:
                os.remove(temp_download_path)
                os.rmdir(os.path.dirname(temp_download_path))
                typer.echo("[poetry-reader] Cleaned up temporary file")
            except Exception:
                pass


@app.command("upload-md")
def upload_md(
    source_dir: Path = typer.Argument(..., help="Directorio con archivos .md a subir"),
    folder_id: Optional[str] = typer.Option(
        None,
        "--folder-id",
        help="ID de la carpeta de destino en Google Drive (si no se especifica, usa markdowns_folder_id del config)",
    ),
    drive_config: Path = typer.Option(
        Path("config/drive_config.yaml"),
        "--drive-config",
        help="Path a la configuración de Google Drive",
    ),
    pattern: str = typer.Option(
        "*.md",
        "--pattern",
        help="Patrón de archivos a subir (default: *.md)",
    ),
    replace: bool = typer.Option(
        False,
        "--replace",
        help="Reemplazar archivos existentes en Drive",
    ),
):
    """
    Sube archivos .md desde una carpeta local a Google Drive.

    Este comando sube todos los archivos markdown desde el directorio especificado
    a una carpeta de destino en Google Drive.

    Examples:
        # Subir todos los .md usando la carpeta configurada en drive_config.yaml
        poetry-reader upload-md ./poemas

        # Subir a una carpeta específica (sobrescribe la configuración)
        poetry-reader upload-md ./poemas --folder-id 1ABC123xyz

        # Subir y reemplazar archivos existentes
        poetry-reader upload-md ./poemas --replace
    """
    import yaml
    from .drive import authenticate, DriveManager

    if not drive_config.exists():
        typer.echo(f"Error: Drive config not found: {drive_config}", err=True)
        typer.echo(
            "Create it with: cp config/drive_config.yaml.example config/drive_config.yaml"
        )
        raise typer.Exit(1)

    if not source_dir.exists():
        typer.echo(f"Error: Source directory not found: {source_dir}", err=True)
        raise typer.Exit(1)

    typer.echo("[poetry-reader] Loading Drive configuration...")
    with open(drive_config) as f:
        drive_cfg = yaml.safe_load(f)

    # Obtener folder_id del config si no se proporcionó
    if folder_id is None:
        folder_id = drive_cfg.get("drive", {}).get("markdowns_folder_id")
        if folder_id is None or folder_id == "YOUR_MARKDOWNS_FOLDER_ID_HERE":
            typer.echo(
                "\nError: markdowns_folder_id not configured in drive_config.yaml",
                err=True,
            )
            typer.echo("Please configure it or use --folder-id option", err=True)
            raise typer.Exit(1)

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

        # Buscar archivos .md
        md_files = list(source_dir.glob(pattern))
        if not md_files:
            typer.echo(f"[poetry-reader] No files found matching pattern: {pattern}")
            raise typer.Exit(0)

        typer.echo(f"[poetry-reader] Found {len(md_files)} files to upload")
        typer.echo(f"[poetry-reader] Destination folder: {folder_id}")
        typer.echo()

        uploaded = 0
        replaced = 0
        failed = 0

        for md_file in md_files:
            try:
                typer.echo(f"  → Uploading: {md_file.name}")

                # Verificar si ya existe
                existing = drive_manager.find_file_by_name(folder_id, md_file.name)

                if existing and replace:
                    typer.echo(f"    → Replacing existing file: {md_file.name}")
                    drive_manager.delete_file(existing.id)
                elif existing:
                    typer.echo(f"    ⚠ Skipping (already exists): {md_file.name}")
                    continue

                # Subir archivo
                file_id = drive_manager.upload_file(
                    str(md_file), folder_id, md_file.name
                )
                typer.echo(f"    ✓ Uploaded: https://drive.google.com/file/d/{file_id}")
                uploaded += 1

            except Exception as e:
                typer.echo(f"    ✗ Failed: {md_file.name} - {e}", err=True)
                failed += 1

        typer.echo()
        typer.echo(f"[poetry-reader] Upload complete!")
        typer.echo(f"  ✓ Uploaded: {uploaded}")
        if replaced > 0:
            typer.echo(f"  ↻ Replaced: {replaced}")
        if failed > 0:
            typer.echo(f"  ✗ Failed: {failed}")

        if failed > 0:
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
