# Poetry Reader con Qwen3-TTS VoiceDesign (CPU)

Generador de videos de poesía utilizando Qwen3-TTS VoiceDesign como motor de voz. Funciona completamente en CPU, sin necesidad de GPU. Permite crear voces personalizadas mediante descripciones en lenguaje natural.

## Características

- **Motor TTS**: Qwen3-TTS VoiceDesign (Alibaba) - Alta calidad, diseño de voz mediante descripciones
- **CPU Only**: Funciona sin GPU, solo requiere CPU
- **Formato**: Videos verticales 9:16 optimizados para TikTok
- **Efectos visuales**: Gradientes animados, partículas, zoom suave
- **Subtítulos**: Sincronización automática con audio
- **Idiomas**: Español e inglés (detección automática)
- **Voz personalizable**: Define la voz mediante instrucciones en texto

## Requisitos

- Docker instalado
- 16GB+ RAM recomendado
- ~10GB de espacio en disco (para el modelo)

## Instalación

### Opción 1: Usando el script helper

```bash
# Construir la imagen
./run.sh build

# Ejecutar
./run.sh run
```

### Opción 2: Usando Docker directamente

```bash
# Construir
docker build -t poetry-reader-qwen3 .

# Ejecutar
docker run \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/models:/app/.cache/huggingface \
  poetry-reader-qwen3 generate /app/data --out /app/output
```

### Opción 3: Usando Docker Compose

```bash
docker-compose up poetry-reader
```

## Uso

### Preparar archivos de entrada

Coloca archivos `.md` en el directorio `data/` con el siguiente formato:

```markdown
Titulo: Nombre del Poema
Autor: Nombre del Autor

Primera línea del poema.
Segunda línea del poema.

Tercera línea después de una pausa.
```

### Generar videos

```bash
# Generar videos desde archivos markdown
./run.sh run

# Con instrucción de voz personalizada
./run.sh run --tts-instruct "Voz femenina suave y melodiosa, tono cálido y pausado"

# Con opciones personalizadas
./run.sh run --palette sunset --font-size 90 --no-particles
```

### Generar solo audio TTS

```bash
# Usando el script helper
./run.sh tts --text "Hola mundo" --instruct "Voz grave y serena de narrador"

# Usando Docker directamente
docker run \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/models:/app/.cache/huggingface \
  poetry-reader-qwen3 tts-generate \
  --text "Tu texto aquí" \
  --instruct "Voz masculina madura, tono tranquilo y pausado" \
  --out /app/output/audio.wav
```

## Instrucciones de voz (VoiceDesign)

Qwen3-TTS VoiceDesign permite definir la voz mediante descripciones en lenguaje natural. Ejemplos:

### Voces masculinas
- `"Voz de hombre maduro, con un registro muy grave y profundo. El tono es extremadamente tranquilo, sereno y reconfortante. Habla de forma pausada, con mucha autoridad suave y una resonancia baja, similar a un narrador de meditación o de documentales de naturaleza."`

- `"Voz masculina joven, clara y enérgica, con tono amigable y dinámico. Perfecta para contenido motivacional."`

### Voces femeninas
- `"Voz femenina cálida y suave, tono medio-alto, melodiosa y pausada. Ideal para narración de cuentos o poesía."`

- `"Voz de mujer adulta, profunda y elegante, con presencia autoritaria pero tranquilizadora."`

### Estilos específicos
- **Narrador documental**: `"Voz grave y pausada, con autoridad informativa, similar a narradores de documentales de naturaleza."`
- **Meditación**: `"Voz muy suave y relajante, tono bajo, habla extremadamente lenta y pausada."`
- **Dinámica**: `"Voz enérgica y expresiva, con variaciones de tono, perfecta para contenido motivacional."`

## Opciones del CLI

### Comando `generate`

```
--out PATH              Directorio de salida (default: output)
--image PATH            Imagen de fondo personalizada
--palette NAME          Paleta de colores: sunset, ocean, forest, lavender, 
                        rose, golden, midnight, peach, mint, autumn
--no-particles          Desactivar partículas
--font-size INT         Tamaño de fuente (default: 80)
--fade-duration FLOAT   Duración del fade (default: 0.5)
--lang CODE             Forzar idioma: es, en
--fps INT               Frames por segundo (default: 30)
--num-particles INT     Número de partículas (default: 80)
--tts-instruct TEXT     Instrucción/descripción de voz para VoiceDesign
--tts-model NAME        Modelo Qwen3-TTS (default: Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign)
--vertical/--horizontal Formato vertical u horizontal
--no-zoom               Desactivar zoom en fondo
```

### Comando `tts-generate`

```
--text TEXT             Texto a sintetizar (requerido)
--instruct TEXT         Descripción/instrucción de voz deseada
--model NAME            Modelo específico (default: Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign)
--device NAME           Device: auto, cpu
--lang CODE             Idioma: es, en (default: es)
--out PATH              Ruta de salida (default: ./out.wav)
```

## Estructura de directorios

```
.
├── data/               # Archivos markdown de entrada
├── output/             # Videos y audios generados
├── models/             # Cache de modelos descargados
├── src/                # Código fuente
├── Dockerfile          # Definición de imagen Docker
├── docker-compose.yml  # Configuración Docker Compose
├── run.sh              # Script helper
└── README.md           # Este archivo
```

## Modelo Qwen3-TTS VoiceDesign

El sistema usa por defecto el modelo `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign`.

- **VoiceDesign**: Permite diseñar voces mediante descripciones en lenguaje natural
- **CustomVoice**: Para usar speakers predefinidos (Ryan, Aiden, etc.)
- **Base**: Para clonación de voz desde audio de referencia

El modelo se descarga automáticamente en el primer uso (~3-4GB) y se cachea en `models/`.

## Solución de problemas

### Out of memory

Si obtienes errores de memoria:
```bash
# Cerrar otras aplicaciones
# O usar un modelo más pequeño (0.6B en lugar de 1.7B)
./run.sh run --tts-model Qwen/Qwen3-TTS-12Hz-0.6B-VoiceDesign
```

### Modelos no se descargan

Verifica conexión a internet y permisos:
```bash
docker run --rm -it poetry-reader-qwen3:latest /bin/bash
# Dentro del contenedor:
python3 -c "from qwen_tts import Qwen3TTSModel; print('OK')"
```

### Error de permisos en volúmenes

```bash
# Crear directorios con permisos correctos
mkdir -p data output models
chmod 777 data output models
```

## Rendimiento en CPU

- **Tiempo de generación**: Aproximadamente 2-3x el tiempo de audio (ej: 30 segundos de audio ≈ 60-90 segundos de procesamiento)
- **Memoria RAM**: ~8-12GB durante la generación
- **Primer uso**: El modelo se descarga automáticamente (~3-4GB)

## Ejemplo completo

```bash
# 1. Crear estructura de directorios
mkdir -p data output models

# 2. Crear archivo de poema
cat > data/mi_poema.md << 'EOF'
Titulo: El Nombre
Autor: Jorge Luis Borges

Si (como afirma el griego en el Cratilo)
el nombre es arquetipo de la cosa
en las letras de rosa está la rosa
y todo el Nilo en la palabra Nilo.
EOF

# 3. Generar video con voz grave y pausada
./run.sh run --tts-instruct "Voz de hombre maduro, con un registro muy grave y profundo. El tono es extremadamente tranquilo, sereno y reconfortante. Habla de forma pausada."

# 4. El video se guardará en output/1_El_Nombre.mp4
```

## Licencia

Este proyecto usa Qwen3-TTS que está bajo licencia Apache-2.0.
