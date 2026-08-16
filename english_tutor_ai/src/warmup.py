"""Warmup script executed during Docker build to bake model weights into the container image."""
import os
import sys

# Disable telemetry
os.environ["MEM0_TELEMETRY"] = "False"

# Ensure src is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def warmup():
    print("[Warmup] Pre-downloading FastEmbed all-MiniLM-L6-v2 ONNX model...")
    try:
        from fastembed import TextEmbedding
        model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
        # Trigger an embedding call to force full graph initialization
        list(model.embed(["Hello world initialization"]))
        print("[Warmup] FastEmbed model downloaded and initialized successfully.")
    except Exception as e:
        print(f"[Warmup Warning] FastEmbed download: {e}")

    print("[Warmup] Pre-downloading Silero VAD model...")
    try:
        from pipecat.audio.vad.silero import SileroVADAnalyzer
        SileroVADAnalyzer()
        print("[Warmup] Silero VAD downloaded successfully.")
    except Exception as e:
        print(f"[Warmup Warning] Silero VAD download: {e}")

    print("[Warmup] Pre-downloading Kokoro TTS model...")
    try:
        from pipecat.services.kokoro.tts import KokoroTTSService
        KokoroTTSService(settings=KokoroTTSService.Settings(voice="af_heart"))
        print("[Warmup] Kokoro TTS downloaded successfully.")
    except Exception as e:
        print(f"[Warmup Warning] Kokoro TTS download: {e}")

    print("[Warmup] All models baked into Docker image successfully!")

if __name__ == "__main__":
    warmup()
