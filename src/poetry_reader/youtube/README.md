# Módulo YouTube para poetry-reader

Este módulo permite subir videos a YouTube usando la API de YouTube Data v3.

## Instalación

Las dependencias ya están incluidas en `pyproject.toml`:
- `google-api-python-client`
- `google-auth-httplib2`
- `google-auth-oauthlib`

## Configuración

### 1. Crear proyecto en Google Cloud Console

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un nuevo proyecto o selecciona uno existente
3. Activa la **YouTube Data API v3**:
   - Ve a "APIs & Services" > "Library"
   - Busca "YouTube Data API v3"
   - Haz clic en "Enable"

### 2. Crear credenciales OAuth 2.0

1. Ve a "APIs & Services" > "Credentials"
2. Haz clic en "Create Credentials" > "OAuth client ID"
3. Selecciona "Desktop app" como tipo de aplicación
4. Descarga el archivo JSON
5. Guárdalo como: `./credentials/youtube_client_secrets.json`

### 3. Configurar pantalla de consentimiento (primera vez)

1. Ve a "APIs & Services" > "OAuth consent screen"
2. Selecciona "External" (o "Internal" si es cuenta Workspace)
3. Completa la información requerida:
   - App name
   - User support email
   - Developer contact email
4. En "Scopes", añade:
   - `https://www.googleapis.com/auth/youtube.upload`
   - `https://www.googleapis.com/auth/youtube.readonly`
5. Agrega tu email como "Test user"

## Uso

### Método 1: Usando la clase YouTubeUploader

```python
from poetry_reader.youtube import YouTubeUploader

# Crear instancia
uploader = YouTubeUploader()

# Subir video
response = uploader.upload_video(
    video_path="/path/to/video.mp4",
    title="Título del video",
    description="Descripción del video",
    tags=["poesía", "poema", "literatura"],
    category_id="27",  # Educación
    privacy_status="private"  # private, unlisted, public
)

print(f"Video subido! ID: {response['id']}")
print(f"URL: https://youtu.be/{response['id']}")
```

### Método 2: Usando la función simple

```python
from poetry_reader.youtube import upload_video

response = upload_video(
    "/path/to/video.mp4",
    title="Mi Video",
    description="Una descripción",
    privacy_status="unlisted"
)
```

### Método 3: Autenticación manual

```python
from poetry_reader.youtube import authenticate

# Obtener servicio autenticado
youtube = authenticate()

# Ahora puedes usar la API directamente
channels_response = youtube.channels().list(
    mine=True,
    part='snippet'
).execute()
```

## Categorías de video

Las categorías disponibles son:

| ID | Categoría |
|----|-----------|
| 1 | Film & Animation |
| 2 | Autos & Vehicles |
| 10 | Music |
| 15 | Pets & Animals |
| 17 | Sports |
| 19 | Travel & Events |
| 20 | Gaming |
| 22 | People & Blogs |
| 23 | Comedy |
| 24 | Entertainment |
| 25 | News & Politics |
| 26 | Howto & Style |
| **27** | **Education** (default) |
| 28 | Science & Technology |
| 29 | Nonprofits & Activism |

## Estados de privacidad

- `private` (default): Solo tú puedes ver el video
- `unlisted`: Cualquiera con el enlace puede verlo
- `public`: Visible para todos

## Manejo de errores

```python
from poetry_reader.youtube import YouTubeAuthError, YouTubeUploadError

try:
    uploader = YouTubeUploader()
    response = uploader.upload_video("video.mp4", title="Test")
except YouTubeAuthError as e:
    print(f"Error de autenticación: {e}")
except YouTubeUploadError as e:
    print(f"Error al subir: {e}")
except FileNotFoundError as e:
    print(f"Archivo no encontrado: {e}")
```

## Notas importantes

1. **Cuota de API**: YouTube tiene límites de cuota. Un upload consume ~1600 unidades.
2. **Autenticación**: La primera vez requiere autenticación manual en navegador.
3. **Credenciales**: Se guardan en `./credentials/youtube_credentials.json` para uso futuro.
4. **Reintentos**: El uploader automáticamente reintenta en errores de servidor.
5. **Progreso**: Se muestra el progreso de subida en la consola.

## Ejemplo completo

```python
#!/usr/bin/env python3
"""Ejemplo de uso del módulo YouTube."""

from pathlib import Path
from poetry_reader.youtube import YouTubeUploader

# Configuración
VIDEO_PATH = "./output/mi_video.mp4"
TITLE = "Mi Poema Favorito"
DESCRIPTION = """Este es un video generado automáticamente.

Incluye:
- Texto del poema
- Narración
- Música de fondo
"""
TAGS = ["poesía", "literatura", "poema", "narración"]

def main():
    # Verificar que existe el video
    if not Path(VIDEO_PATH).exists():
        print(f"Error: No se encuentra {VIDEO_PATH}")
        return
    
    # Crear uploader
    uploader = YouTubeUploader()
    
    # Subir como privado primero
    print("Subiendo video...")
    response = uploader.upload_video(
        video_path=VIDEO_PATH,
        title=TITLE,
        description=DESCRIPTION,
        tags=TAGS,
        category_id="27",  # Educación
        privacy_status="private"
    )
    
    video_id = response['id']
    print(f"\n¡Éxito!")
    print(f"Video ID: {video_id}")
    print(f"URL: https://youtu.be/{video_id}")
    print(f"\nCambia la privacidad a 'public' cuando estés listo.")

if __name__ == "__main__":
    main()
```
