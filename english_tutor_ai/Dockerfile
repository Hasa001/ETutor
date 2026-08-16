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

# Copy dependency specifications
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Expose port (Render/Railway use PORT env var, default to 8000)
ENV PORT=8000
EXPOSE 8000

# Start FastAPI server
CMD ["python", "src/server.py"]
