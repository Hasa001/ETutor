"""Pipeline factory — builds the Pipecat audio processing pipeline."""

from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineParams
from pipecat.pipeline.worker import PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.services.groq.stt import GroqSTTService
from services.resilient_llm import ResilientGroqLLMService
from pipecat.services.kokoro.tts import KokoroTTSService
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketTransport,
)

from config import TutorConfig
from memory import TutorMemory
from prompts import generate_tutor_system_prompt
from processors.bot_speaking_gate import BotSpeakingGateProcessor


async def create_tutor_pipeline(
    transport: FastAPIWebsocketTransport,
    user_id: str,
    memory_db: TutorMemory,
    tts: KokoroTTSService,
    vad: SileroVADAnalyzer,
    config: TutorConfig,
) -> tuple[PipelineWorker, LLMContext]:
    """Construct the full voice-AI pipeline using pre-warmed model instances.

    Args:
        transport: Pre-configured WebSocket transport.
        user_id: Student identifier for memory retrieval.
        memory_db: TutorMemory instance (pre-warmed at startup).
        tts: Pre-warmed KokoroTTSService instance.
        vad: Pre-warmed SileroVADAnalyzer instance.
        config: Application configuration.

    Returns:
        A tuple of (PipelineTask, LLMContext).
    """
    # --- 1. Fetch student profile from long-term memory ----
    logger.info("Fetching student profile for '{}'", user_id)
    profile: str = await memory_db.get_student_profile(user_id)

    # --- 2. Generate system prompt ----
    system_prompt: str = generate_tutor_system_prompt(profile)
    logger.debug("System prompt generated ({} chars)", len(system_prompt))

    # --- 3. Build LLM context ----
    context = LLMContext(
        messages=[{"role": "system", "content": system_prompt}]
    )

    # --- 4. Reuse pre-warmed VAD (no model load per connection) ----
    logger.info(
        "Reusing shared VAD (confidence={}, stop_secs={}, start_secs={})",
        config.VAD_CONFIDENCE,
        config.VAD_STOP_SECS,
        config.VAD_START_SECS,
    )

    # --- 5. Initialize STT & LLM (stateless — safe to create per connection) ----
    stt = GroqSTTService(
        api_key=config.GROQ_API_KEY,
        settings=GroqSTTService.Settings(
            model="whisper-large-v3",
            language="en",
        ),
    )
    logger.info("STT service ready (Groq Whisper)")

    llm = ResilientGroqLLMService(
        api_key=config.GROQ_API_KEY,
        primary_model="groq/compound",
        fallback_models=["groq/compound-mini", "llama-3.1-8b-instant", "openai/gpt-oss-120b", "openai/gpt-oss-20b"],
        max_tokens=200,
    )
    logger.info("LLM service ready (Resilient Groq Compound with Instant fallbacks)")

    logger.info("Reusing pre-warmed Kokoro TTS service")

    # --- 6. Create context aggregator with shared VAD ----
    context_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=vad,
        ),
    )

    # --- 7. Build the echo-suppression gate ---
    echo_gate = BotSpeakingGateProcessor(
        holdoff_secs=config.VAD_HOLDOFF_SECS,
        name="BotEchoGate",
    )

    # --- 8. Assemble pipeline — uses shared pre-warmed tts & vad ----
    pipeline = Pipeline(
        [
            transport.input(),
            echo_gate,          # ← Mutes mic during bot speech + holdoff
            stt,
            context_aggregator.user(),
            llm,
            tts,                # ← Pre-warmed, reused across connections
            transport.output(),
            context_aggregator.assistant(),
        ]
    )
    logger.info("Pipeline assembled: Input → EchoGate → STT → LLM → TTS → Output")

    # --- 8. Create worker with sample rate config ----
    task = PipelineWorker(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=config.AUDIO_IN_SAMPLE_RATE,
            audio_out_sample_rate=config.AUDIO_OUT_SAMPLE_RATE,
        ),
    )
    logger.success("Pipeline task created with VAD-based interruption support")

    return task, context
