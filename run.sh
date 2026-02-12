#!/bin/bash

# Script para facilitar el uso de Poetry Reader con Qwen3-TTS (solo CPU)

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Poetry Reader con Qwen3-TTS (CPU) ===${NC}"

# Verificar si docker está instalado
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker no está instalado${NC}"
    exit 1
fi

# Función para mostrar ayuda
show_help() {
    echo "Uso: $0 [comando] [opciones]"
    echo ""
    echo "Comandos:"
    echo "  build       - Construir la imagen Docker"
    echo "  run         - Ejecutar generación de videos"
    echo "  tts         - Generar solo audio TTS"
    echo "  shell       - Abrir shell en el contenedor"
    echo "  help        - Mostrar esta ayuda"
    echo ""
    echo "Ejemplos:"
    echo "  $0 build"
    echo "  $0 run"
    echo "  $0 tts --text 'Hola mundo' --instruct 'Voz grave y pausada'"
}

# Comando build
build() {
    echo -e "${YELLOW}Construyendo imagen Docker...${NC}"
    docker build -t poetry-reader-qwen3:latest .
    echo -e "${GREEN}✓ Imagen construida exitosamente${NC}"
}

# Comando run
run() {
    echo -e "${YELLOW}Ejecutando con CPU...${NC}"
    docker run --rm \
        -v "$(pwd)/data:/app/data" \
        -v "$(pwd)/output:/app/output" \
        -v "$(pwd)/models:/app/.cache/huggingface" \
        -e CUDA_VISIBLE_DEVICES="" \
        poetry-reader-qwen3:latest \
        generate /app/data --out /app/output "$@"
}

# Comando tts
tts() {
    echo -e "${YELLOW}Generando audio TTS...${NC}"
    docker run --rm \
        -v "$(pwd)/output:/app/output" \
        -v "$(pwd)/models:/app/.cache/huggingface" \
        -e CUDA_VISIBLE_DEVICES="" \
        poetry-reader-qwen3:latest \
        tts-generate --out /app/output/tts_output.wav "$@"
    echo -e "${GREEN}✓ Audio guardado en output/tts_output.wav${NC}"
}

# Comando shell
shell() {
    echo -e "${YELLOW}Abriendo shell en el contenedor...${NC}"
    docker run --rm -it \
        -v "$(pwd)/data:/app/data" \
        -v "$(pwd)/output:/app/output" \
        -v "$(pwd)/models:/app/.cache/huggingface" \
        -e CUDA_VISIBLE_DEVICES="" \
        poetry-reader-qwen3:latest \
        /bin/bash
}

# Procesar comandos
case "${1:-help}" in
    build)
        build
        ;;
    run)
        shift
        run "$@"
        ;;
    tts)
        shift
        tts "$@"
        ;;
    shell)
        shell
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}Comando desconocido: $1${NC}"
        show_help
        exit 1
        ;;
esac
