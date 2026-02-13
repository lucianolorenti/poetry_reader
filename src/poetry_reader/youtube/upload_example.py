#!/usr/bin/env python3
"""
Ejemplo de uso del módulo YouTube para subir videos.

Este es un script de ejemplo independiente que muestra cómo usar el módulo.
No está integrado con el resto del sistema poetry-reader.
"""

import sys
import argparse
from pathlib import Path

# Asegurar que podemos importar desde src
sys.path.insert(0, str(Path(__file__).parent.parent))

from poetry_reader.youtube import YouTubeUploader, upload_video
from poetry_reader.youtube.uploader import YouTubeUploader as YTUploader


def main():
    parser = argparse.ArgumentParser(
        description="Subir videos a YouTube usando el módulo poetry_reader.youtube"
    )
    parser.add_argument("video", type=str, help="Ruta al archivo de video a subir")
    parser.add_argument(
        "--title",
        "-t",
        type=str,
        default=None,
        help="Título del video (usa el nombre del archivo si no se especifica)",
    )
    parser.add_argument(
        "--description",
        "-d",
        type=str,
        default="Video subido desde poetry-reader",
        help="Descripción del video",
    )
    parser.add_argument(
        "--privacy",
        "-p",
        choices=["private", "unlisted", "public"],
        default="private",
        help="Estado de privacidad del video (default: private)",
    )
    parser.add_argument(
        "--tags",
        type=str,
        nargs="+",
        default=["poesía", "poema"],
        help="Tags para el video (separados por espacio)",
    )
    parser.add_argument(
        "--category",
        "-c",
        type=str,
        default="27",
        help="ID de categoría (default: 27 - Educación)",
    )

    args = parser.parse_args()

    # Verificar que el video existe
    video_path = Path(args.video)
    if not video_path.exists():
        print(f"❌ Error: No se encuentra el video: {video_path}")
        sys.exit(1)

    # Generar título si no se proporcionó
    title = args.title
    if title is None:
        title = video_path.stem.replace("_", " ").replace("-", " ").title()

    print("=" * 60)
    print("🎬 YouTube Uploader - Poetry Reader")
    print("=" * 60)
    print()
    print(f"📁 Video: {video_path}")
    print(f"📝 Título: {title}")
    print(f"📄 Descripción: {args.description}")
    print(f"🏷️  Tags: {', '.join(args.tags)}")
    print(f"🔒 Privacidad: {args.privacy}")
    print()

    try:
        # Crear uploader y subir
        uploader = YTUploader()

        print("🚀 Iniciando subida...")
        print("(La primera vez requerirá autenticación OAuth)")
        print()

        response = uploader.upload_video(
            video_path=str(video_path),
            title=title,
            description=args.description,
            tags=args.tags,
            category_id=args.category,
            privacy_status=args.privacy,
        )

        video_id = response["id"]

        print()
        print("=" * 60)
        print("✅ ¡Video subido exitosamente!")
        print("=" * 60)
        print()
        print(f"🆔 Video ID: {video_id}")
        print(f"🔗 URL: https://youtu.be/{video_id}")
        print()

    except Exception as e:
        print()
        print("=" * 60)
        print("❌ Error al subir el video")
        print("=" * 60)
        print(f"{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
