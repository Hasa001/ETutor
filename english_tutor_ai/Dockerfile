FROM python:3.13-slim

# Install system audio and build dependencies for Kokoro & PyAudio
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    libasound2-dev \
    portaudio19-dev \
    espeak-ng \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Ensure python finds modules in src/ and root
ENV PYTHONPATH=/app/src:/app
ENV PYTHONUNBUFFERED=1

# Copy dependency specifications
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Pre-download and cache all neural model weights into the container image
RUN python src/warmup.py

# Expose port (Render/Railway dynamically supply PORT)
ENV PORT=8000
EXPOSE 8000

# Start FastAPI server directly with python
CMD ["python", "src/server.py"]
