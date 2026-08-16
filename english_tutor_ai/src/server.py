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
models_loading_error: str | None = None

models_ready_event = asyncio.Event()

def _load_models_sync():
    """Heavy model initialization executed in a worker thread so the event loop never blocks."""
    global memory_db, tts_service, vad_analyzer, models_loading_error
    t0 = time.monotonic()
    logger.info("Background model pre-warming started in worker thread...")

    try:
        # 1. Initialize Mem0 & embeddings (uses baked-in weights)
        logger.info("Loading Mem0 memory engine...")
        memory_db = TutorMemory(config)

        # 2. Initialize Silero VAD
        logger.info("Loading Silero VAD model...")
        vad_analyzer = SileroVADAnalyzer(
            params=VADParams(
                confidence=config.VAD_CONFIDENCE,
                start_secs=config.VAD_START_SECS,
                stop_secs=config.VAD_STOP_SECS,
                min_volume=config.VAD_MIN_VOLUME,
            )
        )

        # 3. Initialize Kokoro TTS
        logger.info("Loading Kokoro TTS model...")
        tts_service = KokoroTTSService(
            settings=KokoroTTSService.Settings(voice="af_heart")
        )

        elapsed = time.monotonic() - t0
        logger.success(f"All models pre-warmed in {elapsed:.1f}s. Voice engine fully ready.")
    except Exception as e:
        logger.error(f"Error during background model loading: {e}")
        models_loading_error = str(e)
    finally:
        models_ready_event.set()

async def init_models_background():
    """Async wrapper that offloads heavy CPU/network model loading to a background thread."""
    await asyncio.to_thread(_load_models_sync)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start pre-warming in background task so port binds in <10ms
    asyncio.create_task(init_models_background())
    logger.info("FastAPI server started. Port is now open and listening.")
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
    is_ready = (
        models_ready_event.is_set()
        and memory_db is not None
        and tts_service is not None
        and vad_analyzer is not None
    )
    return {
        "status": "healthy",
        "service": "ETutor AI Voice Backend",
        "models_ready": is_ready,
        "error": models_loading_error,
    }

@app.websocket("/ws")
@app.websocket("/")
async def websocket_endpoint(websocket: WebSocket, user_id: str = "default_student_1"):
    await websocket.accept()
    if not models_ready_event.is_set():
        logger.info("Client connected while models are warming up; waiting up to 60s...")
        try:
            await asyncio.wait_for(models_ready_event.wait(), timeout=60.0)
        except asyncio.TimeoutError:
            logger.error("Timed out waiting for models to load")
            await websocket.close(code=1011, reason="Models initialization timeout")
            return

    if memory_db is None or tts_service is None or vad_analyzer is None:
        err = models_loading_error or "Voice engine models are not ready."
        logger.error(f"Connection rejected for {user_id}: {err}")
        await websocket.close(code=1011, reason=f"Init error: {err}")
        return

    logger.info(f"Client connected and models verified ready for user_id: {user_id}")

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

        # Explicit garbage collection to free memory on 512MB RAM instance
        import gc
        gc.collect()

if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
