import asyncio
from contextlib import asynccontextmanager
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)
from pipecat.serializers.protobuf import ProtobufFrameSerializer
from pipecat.services.kokoro.tts import KokoroTTSService
from pipecat.workers.runner import WorkerRunner

from dotenv import load_dotenv
load_dotenv()

from config import TutorConfig
from memory import TutorMemory
from pipeline import create_tutor_pipeline
from pipecat.frames.frames import TTSSpeakFrame

config = TutorConfig()  # type: ignore[call-arg]
memory_db: TutorMemory = None  # type: ignore
tts_service: KokoroTTSService = None  # type: ignore
vad_analyzer: SileroVADAnalyzer = None  # type: ignore

@asynccontextmanager
async def lifespan(app: FastAPI):
    global memory_db, tts_service, vad_analyzer
    t0 = time.monotonic()
    logger.info("Initializing application resources...")

    # --- Pre-warm Mem0 (loads HuggingFace embedder + Qdrant) ---
    logger.info("Loading Mem0 memory engine...")
    memory_db = TutorMemory(config)

    # --- Pre-warm Silero VAD (downloads ONNX on first run) ---
    logger.info("Loading Silero VAD model...")
    vad_analyzer = SileroVADAnalyzer(
        params=VADParams(
            confidence=config.VAD_CONFIDENCE,
            start_secs=config.VAD_START_SECS,
            stop_secs=config.VAD_STOP_SECS,
            min_volume=config.VAD_MIN_VOLUME,
        )
    )

    # --- Pre-warm Kokoro TTS (loads neural TTS model into RAM) ---
    logger.info("Loading Kokoro TTS model...")
    tts_service = KokoroTTSService(
        settings=KokoroTTSService.Settings(voice="af_heart")
    )

    elapsed = time.monotonic() - t0
    logger.success(f"All models pre-warmed in {elapsed:.1f}s. Server ready.")
    yield
    logger.info("Cleaning up application resources...")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
@app.get("/health")
async def health_check():
    """Health check endpoint for cloud load balancers and port scanners."""
    return {"status": "healthy", "service": "ETutor AI Voice Backend"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, user_id: str = "default_student_1"):
    await websocket.accept()
    logger.info(f"Client connected for user_id: {user_id}")

    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_in_sample_rate=config.AUDIO_IN_SAMPLE_RATE,
            audio_out_sample_rate=config.AUDIO_OUT_SAMPLE_RATE,
            serializer=ProtobufFrameSerializer(),
        ),
    )

    task, context = await create_tutor_pipeline(
        transport=transport,
        user_id=user_id,
        memory_db=memory_db,
        tts=tts_service,
        vad=vad_analyzer,
        config=config,
    )

    runner = WorkerRunner()
    await runner.add_workers(task)
    
    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info(f"Client connection established for {user_id}. Queuing initial greeting...")
        await task.queue_frames([
            TTSSpeakFrame(text="Hello! I am your English tutor. What would you like to talk about today?")
        ])

    try:
        logger.info("Pipeline running for websocket client...")
        await runner.run()
    except Exception as e:
        logger.error(f"Pipeline crashed: {e}")
    finally:
        # Save session memories after they disconnect
        if len(context.messages) > 1:
            logger.info(f"Saving session memories for {user_id}...")
            await memory_db.extract_session_memories(context.messages, user_id)
            logger.success("Session memories saved successfully")
        else:
            logger.info("No conversation to save")

if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
