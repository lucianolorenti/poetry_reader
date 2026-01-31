Proyecto: Generador de videos desde Excel

Estructura
- Código fuente en `src/poetry_reader/`.
- Entrada CLI: `src/poetry_reader/cli.py` (usa `typer`).

Dependencias
- Este proyecto usa `uv` para manejar dependencias; no pongas dependencias directas en `requirements.txt`.
- Asegúrate de instalar dependencias con `uv` según tu flujo de trabajo.

Uso
- Ejecutar desde la raíz del repo:
  - `python -m src.poetry_reader.cli generate tus_textos.xlsx --out output --image fondo.jpg`
  - o `python -m poetry_reader.cli generate ...` si instalas el paquete en editable mode.

Notas
- Necesitas `ffmpeg` instalado en el sistema para que MoviePy funcione.
- Coqui TTS (`TTS`) descargará modelos la primera vez que se ejecute.

Si quieres que haga un `setup.py` o `pyproject.toml` para integrar mejor con `uv`, dímelo y lo configuro.
