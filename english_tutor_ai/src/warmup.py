"""Warmup script executed during Docker build to bake lightweight model weights into the container image."""
import os
import sys
import urllib.request
from pathlib import Path

# Disable telemetry
os.environ["MEM0_TELEMETRY"] = "False"

# Ensure src is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def warmup():
    print("[Warmup] 1/3 Pre-downloading FastEmbed ONNX model...")
    try:
        from fastembed import TextEmbedding
        model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
        list(model.embed(["Hello world warm up"]))
        print("[Warmup] FastEmbed model initialized successfully.")
    except Exception as e:
        print(f"[Warmup Warning] FastEmbed download: {e}")

    print("[Warmup] 2/3 Pre-downloading Silero VAD model...")
    try:
        from pipecat.audio.vad.silero import SileroVADAnalyzer
        SileroVADAnalyzer()
        print("[Warmup] Silero VAD downloaded successfully.")
    except Exception as e:
        print(f"[Warmup Warning] Silero VAD download: {e}")

    print("[Warmup] 3/3 Pre-downloading lightweight Kokoro INT8 (88MB) ONNX model...")
    try:
        from pipecat.services.kokoro.tts import KOKORO_CACHE_DIR, KokoroTTSService
        KOKORO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        int8_file = KOKORO_CACHE_DIR / "kokoro-v1.0.int8.onnx"
        voices_file = KOKORO_CACHE_DIR / "voices-v1.0.bin"

        if not int8_file.exists():
            print(f"[Warmup] Downloading {int8_file.name}...")
            urllib.request.urlretrieve(
                "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx",
                int8_file,
            )

        if not voices_file.exists():
            print(f"[Warmup] Downloading {voices_file.name}...")
            urllib.request.urlretrieve(
                "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
                voices_file,
            )

        # Initialize to verify ONNX graph
        KokoroTTSService(
            model_path=str(int8_file),
            voices_path=str(voices_file),
            settings=KokoroTTSService.Settings(voice="af_heart"),
        )
        print("[Warmup] Kokoro INT8 TTS initialized successfully.")
    except Exception as e:
        print(f"[Warmup Warning] Kokoro TTS download: {e}")

    print("[Warmup] All models baked into Docker image successfully!")

if __name__ == "__main__":
    warmup()
