# Poetry Reader Agent Guidelines

AI agent instructions for the Poetry Reader project - a Python CLI tool that converts markdown poetry files into TikTok-ready videos with AI voice narration using Qwen3-TTS.

## Project Overview

- **Language**: Python 3.12+
- **Package Manager**: uv (not pip)
- **Build System**: uv_build
- **Linter**: Ruff
- **CLI Framework**: Typer
- **Main Entry**: `poetry-reader` command (defined in `pyproject.toml`)

## Build/Lint/Test Commands

```bash
# Install dependencies
uv sync

# Run the CLI
poetry-reader --help

# Run with explicit module
python -m poetry_reader

# Lint with ruff
ruff check .
ruff check --fix .        # Auto-fix issues

# Format with ruff
ruff format .

# No formal test suite exists - test manually with:
poetry-reader generate ./poemas --out ./output --tts-reference-wav assets/voice_reference.wav
```

**Note**: There is no pytest or test runner configured. Test manually using the CLI commands.

## Code Style Guidelines

### Imports

Order imports in three groups with blank lines between:

1. **Standard library** (os, typing, pathlib, etc.)
2. **Third-party packages** (typer, moviepy, torch, etc.)
3. **Local project imports** (from .module import ...)

Example:

```python
import os
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path
from dataclasses import dataclass

import typer
from moviepy.audio.io.AudioFileClip import AudioFileClip
import torch

from .ttsgenerator import get_tts
from .utils import parse_md_file
```

### Formatting

- **Indentation**: 4 spaces (no tabs)
- **Line length**: ~100 characters (Ruff default)
- **Quotes**: Use double quotes for strings (`"string"`)
- **Trailing commas**: Use in multi-line collections
- **Blank lines**: 2 between top-level functions/classes, 1 between methods

### Type Hints

Always use type hints for:
- Function parameters
- Return values
- Class attributes

```python
def process_file(
    file_path: Path,
    options: Optional[Dict[str, Any]] = None,
    verbose: bool = False
) -> ProcessingResult:
    """Process a single file."""
    ...
```

Use `from __future__ import annotations` for forward references if needed (Python 3.12 has PEP 649).

### Naming Conventions

| Entity | Convention | Example |
|--------|-----------|---------|
| Functions/Variables | snake_case | `generate_video()` |
| Classes | PascalCase | `VideoGenerator` |
| Constants | UPPER_SNAKE_CASE | `MAX_RETRIES` |
| Private methods | _leading_underscore | `_internal_helper()` |
| Modules | snake_case | `video_generator.py` |
| Packages | snake_case | `poetry_reader/` |

### Docstrings

Use Google-style docstrings with Args/Returns/Raises sections:

```python
def upload_file(
    self,
    local_path: str,
    drive_folder_id: str,
    filename: Optional[str] = None
) -> str:
    """Upload a file to Google Drive.

    Args:
        local_path: Path to local file to upload
        drive_folder_id: Google Drive folder ID where file will be uploaded
        filename: Optional custom filename (default: use local filename)

    Returns:
        str: Google Drive file ID of uploaded file

    Raises:
        DriveManagerError: If upload fails after retries
    """
```

### Error Handling

1. **Use custom exceptions** for domain-specific errors:

```python
class DriveManagerError(Exception):
    """Raised when Drive operations fail."""
    pass
```

2. **Chain exceptions** with `from` for context:

```python
try:
    file.FetchMetadata()
except Exception as e:
    raise DriveManagerError(f"Failed to get metadata: {e}") from e
```

3. **Use logging**, not print statements for internal code:

```python
LOGGER = logging.getLogger(__name__)
LOGGER.info("Processing batch %d", batch_num)
LOGGER.warning("Sample rate mismatch detected")
LOGGER.error("Upload failed: %s", error_msg)
```

4. **CLI commands** should use `typer.echo()` for user-facing output with `[poetry-reader]` prefix.

### Logging Format

Configure logging at module level:

```python
logging.basicConfig(
    level=logging.INFO,
    format="[%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
LOGGER = logging.getLogger(__name__)
```

### Path Handling

Always use `pathlib.Path` instead of string paths:

```python
from pathlib import Path

# Good
output_dir = Path("./output")
output_dir.mkdir(parents=True, exist_ok=True)
file_path = output_dir / "video.mp4"

# Bad
output_dir = "./output"
os.makedirs(output_dir, exist_ok=True)
file_path = os.path.join(output_dir, "video.mp4")
```

### File Organization

- Keep modules focused and cohesive
- Maximum ~500 lines per file (split if larger)
- Place utilities in `utils.py`
- Use `__init__.py` to expose public API

### Language for Comments/Messages

- **Code comments**: English
- **CLI output**: Spanish (with `[poetry-reader]` prefix)
- **Docstrings**: English

Example:

```python
# Process each block sequentially
typer.echo("[poetry-reader] Procesando bloques...")  # User sees Spanish
```

### Dataclasses for Data

Use `@dataclass` for structured data:

```python
@dataclass
class ProcessingResult:
    """Result of processing a single markdown."""
    titulo: str
    autor: str
    status: str  # 'success', 'failed', 'skipped'
    video_id: Optional[str] = None
    error: Optional[str] = None
```

### Configuration

Store configuration in YAML files under `config/`:

- `config/video_defaults.yaml` - Video generation settings
- `config/drive_config.yaml` - Google Drive settings (gitignored)

### CLI Commands

Add new commands to `cli.py` using Typer:

```python
@app.command()
def my_command(
    input_dir: Path = typer.Argument(..., help="Directorio de entrada"),
    verbose: bool = typer.Option(False, "--verbose", help="Modo verbose"),
):
    """Descripción del comando en docstring."""
    typer.echo(f"[poetry-reader] Procesando {input_dir}...")
```

## Common Patterns

### Retry Logic with Exponential Backoff

```python
for attempt in range(self.max_retries):
    try:
        result = operation()
        return result
    except Exception as e:
        if attempt < self.max_retries - 1:
            time.sleep(self.retry_delay * (attempt + 1))
        else:
            raise DriveManagerError(f"Failed: {e}") from e
```

### Batch Processing

```python
def process_batch(items: List[Item], batch_size: int = 5):
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        process_chunk(batch)
        if torch.cuda.is_available():
            torch.cuda.empty_cache()  # Clear GPU memory
```

### Temporary Directories

```python
import tempfile
with tempfile.TemporaryDirectory() as tmpdir:
    temp_path = Path(tmpdir) / "file.txt"
    # Use temp_path...
# Automatically cleaned up
```

## Important Notes

- **TTS requires reference WAV**: Set `tts_reference_wav` in config or CLI
- **CUDA GPU recommended**: 8GB+ VRAM for 1.7B model, 3GB minimum for 0.6B
- **Video format**: 1080x1920 (9:16 vertical) for TikTok by default
- **Markdown format**: Must have `Titulo:` and `Autor:` headers
- **Always run ruff before committing**: `ruff check . && ruff format .`
