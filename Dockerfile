FROM python:3.11-slim-bookworm

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV CUDA_VISIBLE_DEVICES=""

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    git-lfs \
    ffmpeg \
    libsndfile1 \
    wget \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml /app/
COPY src /app/src
COPY data /app/data
COPY README.md /app/

# Install poetry_reader dependencies
RUN pip install --no-cache-dir -e .

# Install qwen-tts
RUN pip install --no-cache-dir qwen-tts

# Create directories for data and output
RUN mkdir -p /app/data /app/output

# Set environment variables
ENV PYTHONPATH=/app/src:$PYTHONPATH
ENV HF_HOME=/app/.cache/huggingface

# Default command
ENTRYPOINT ["poetry-reader"]
CMD ["--help"]
