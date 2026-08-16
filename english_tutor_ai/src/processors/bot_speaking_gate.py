"""
BotSpeakingGateProcessor — Prevents the pipeline from processing
microphone audio frames while the bot is actively speaking.

This solves the acoustic echo / self-response loopback problem where the
bot's TTS audio plays through speakers, gets picked up by the user's mic,
transcribed by the STT, and then fed back into the LLM.

Strategy:
  - Observe BotStartedSpeakingFrame → enter GATED mode:
      • Drop all InputAudioRawFrame so VAD and STT see no audio.
      • Apply a hold-off period after bot stops speaking to absorb
        microphone capture latency / acoustic tail.
  - Observe BotStoppedSpeakingFrame → start hold-off timer, then open gate.
"""

import asyncio
from dataclasses import dataclass

from loguru import logger

from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    Frame,
    InputAudioRawFrame,
    SystemFrame,
)
from pipecat.pipeline.pipeline import FrameDirection
from pipecat.processors.frame_processor import FrameProcessor


@dataclass
class _GateState:
    bot_is_speaking: bool = False
    # Seconds to keep the gate closed after bot finishes speaking to absorb
    # microphone capture latency and acoustic reverb tail.
    holdoff_secs: float = 0.8
    _holdoff_task: asyncio.Task | None = None


class BotSpeakingGateProcessor(FrameProcessor):
    """Drops InputAudioRawFrames while the bot is speaking (+ hold-off period).

    Insert this between transport.input() and the STT service:

        Pipeline([
            transport.input(),
            BotSpeakingGateProcessor(holdoff_secs=0.8),
            stt,
            ...
        ])

    Args:
        holdoff_secs: How long after `BotStoppedSpeakingFrame` to continue
            suppressing microphone audio. Absorbs acoustic reverb / mic latency.
            Defaults to 0.8 seconds.
    """

    def __init__(self, holdoff_secs: float = 0.8, **kwargs):
        super().__init__(**kwargs)
        self._state = _GateState(holdoff_secs=holdoff_secs)
        self._dropped_frames = 0

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        # ── Bot started speaking ──────────────────────────────────────────────
        if isinstance(frame, BotStartedSpeakingFrame):
            self._state.bot_is_speaking = True

            # Cancel any pending hold-off timer — bot is speaking again
            if self._state._holdoff_task and not self._state._holdoff_task.done():
                self._state._holdoff_task.cancel()
                self._state._holdoff_task = None

            logger.debug("BotSpeakingGate: CLOSED — suppressing mic input")
            await self.push_frame(frame, direction)
            return

        # ── Bot stopped speaking ──────────────────────────────────────────────
        if isinstance(frame, BotStoppedSpeakingFrame):
            self._state.bot_is_speaking = False
            await self.push_frame(frame, direction)

            # Start hold-off timer before reopening the gate
            self._state._holdoff_task = self.create_task(
                self._open_gate_after_holdoff()
            )
            return

        # ── Gate logic: drop mic audio while bot is speaking or in hold-off ──
        if isinstance(frame, InputAudioRawFrame):
            if self._state.bot_is_speaking or self._state._holdoff_task is not None:
                self._dropped_frames += 1
                if self._dropped_frames % 50 == 0:
                    logger.debug(
                        f"BotSpeakingGate: dropped {self._dropped_frames} mic frames "
                        "(bot echo suppression active)"
                    )
                # Drop frame — do NOT push downstream
                return

        # ── All other frames pass through ─────────────────────────────────────
        await self.push_frame(frame, direction)

    async def _open_gate_after_holdoff(self):
        """Sleep for holdoff_secs then clear the hold-off task to open the gate."""
        try:
            await asyncio.sleep(self._state.holdoff_secs)
            logger.debug(
                f"BotSpeakingGate: OPEN after {self._state.holdoff_secs}s hold-off "
                f"(dropped {self._dropped_frames} echo frames this session)"
            )
            self._dropped_frames = 0
        except asyncio.CancelledError:
            # Bot started speaking again before hold-off expired — keep gate closed
            pass
        finally:
            self._state._holdoff_task = None
