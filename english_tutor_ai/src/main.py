"""Application entry point — launches the real-time voice English tutor."""

import asyncio
import sys
import warnings

# Suppress non-actionable internal deprecation warnings from upstream libraries (Pipecat / Mem0)
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

from dotenv import load_dotenv
from loguru import logger

from pipecat.transports.local.audio import (
    LocalAudioTransport,
    LocalAudioTransportParams,
)
from pipecat.workers.runner import WorkerRunner

from config import TutorConfig
from memory import TutorMemory
from pipeline import create_tutor_pipeline


async def main() -> None:
    """Initialise services and run the voice-AI pipeline."""
    # --- Load environment & config ----
    load_dotenv()
    config = TutorConfig()  # type: ignore[call-arg]  # reads from .env
    user_id: str = config.USER_ID

    logger.info("Starting English Tutor AI for user '{}'", user_id)

    # --- Initialise memory layer ----
    memory_db = TutorMemory(config)

    # --- Initialise audio transport ----
    # Note: VAD is configured in the LLMContextAggregatorPair, not the transport.
    transport = LocalAudioTransport(
        params=LocalAudioTransportParams(
            audio_in_enabled=True,
            audio_in_sample_rate=config.AUDIO_IN_SAMPLE_RATE,
            audio_out_enabled=True,
            audio_out_sample_rate=config.AUDIO_OUT_SAMPLE_RATE,
        )
    )
    logger.info(
        "Audio transport ready (in={}Hz, out={}Hz)",
        config.AUDIO_IN_SAMPLE_RATE,
        config.AUDIO_OUT_SAMPLE_RATE,
    )

    # --- Build pipeline ----
    task, context = await create_tutor_pipeline(
        transport=transport,
        user_id=user_id,
        memory_db=memory_db,
        config=config,
    )

    # --- Run ----
    runner = WorkerRunner()
    await runner.add_workers(task)
    try:
        logger.info("Pipeline running — speak into your microphone! (Ctrl+C to stop)")
        await runner.run()
    except KeyboardInterrupt:
        logger.info("Session interrupted by user")
    except Exception:
        logger.opt(exception=True).error("Pipeline crashed unexpectedly")
    finally:
        # Persist conversation memories if there was a meaningful session
        if len(context.messages) > 1:
            logger.info(
                "Saving session memories ({} messages)…",
                len(context.messages),
            )
            await memory_db.extract_session_memories(
                context.messages, user_id
            )
            logger.success("Session memories saved successfully")
        else:
            logger.info("No conversation to save (session was too short)")

        logger.info("Goodbye!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
