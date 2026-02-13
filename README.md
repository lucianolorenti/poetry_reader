# Poetry Reader

Converts markdown poetry files into TikTok-ready videos with AI voice narration.

## What it does

- Reads markdown files with poem metadata (title, author, text)
- Generates audio using Qwen3-TTS with voice cloning
- Creates vertical 9:16 videos (1080x1920) with animated backgrounds
- Optionally uploads to Google Drive and tracks progress in Excel

## Requirements

- Python 3.12+
- CUDA GPU (8GB+ VRAM recommended, 3GB minimum)
- ffmpeg
- uv (package manager)

## Setup

```bash
uv sync
```

## Configuration

Create your voice reference file:

```bash
poetry-reader generate-voice-reference \
  --instruct "Deep, calm poetry narrator voice" \
  --out assets/voice_reference.wav
```

Edit `config/video_defaults.yaml` and set:

```yaml
video:
  tts_reference_wav: "assets/voice_reference.wav"
```

## Usage

### Single video

```bash
poetry-reader generate ./poemas \
  --out ./output \
  --tts-reference-wav assets/voice_reference.wav
```

### Batch from Google Drive

Create this folder structure in Google Drive:

```
📁 Poetry Videos/
├── 📁 markdowns/          # Drop poem files here (.md)
├── 📁 videos/             # Generated videos appear here
└── 📄 tracker.xlsx        # Processing status
```

**Excel tracker format** (columns):
- `Autor` - Author name
- `Titulo` - Poem title  
- `Texto` - Poem content (auto-filled)
- `Hecho` - TRUE/FALSE (processed status)
- `video_drive_id` - Video file ID (auto-filled)
- `fecha_procesado` - Processing date (auto-filled)
- `error` - Error message if failed

**Poem file format** (markdown):
```markdown
---
title: "Poem Title"
author: "Author Name"
---

Poem text here...
Multiple lines supported.
```

**Setup:**
1. Create the folders above in Google Drive
2. Copy `config/drive_config.yaml.example` to `config/drive_config.yaml`
3. Fill in your folder/file IDs from Google Drive URLs
4. Place `client_secrets.json` in `./credentials/` (from Google Cloud Console)
5. Run:

```bash
poetry-reader process-drive
```

## Markdown format

```markdown
---
title: "Poem Title"
author: "Author Name"
---

Poem text here...
```

---

Vibecoded with love by Luciano Lorenti
