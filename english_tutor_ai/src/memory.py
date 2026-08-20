"""Student long-term memory engine — optimized for low-memory cloud deployments."""

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from groq import AsyncGroq
from loguru import logger

from config import TutorConfig

MEMORY_FILE_PATH = Path("student_memories.json")


class TutorMemory:
    """Manages student-specific long-term memory and learning profiles.

    Uses cloud-based Groq LLM for fact extraction and lightweight persistent
    JSON storage for memory recall, eliminating local vector store RAM overhead.
    """

    def __init__(self, config: TutorConfig) -> None:
        self.config = config
        self._groq_client: AsyncGroq | None = None
        if config.GROQ_API_KEY:
            try:
                self._groq_client = AsyncGroq(api_key=config.GROQ_API_KEY)
            except Exception as e:
                logger.warning(f"Failed to initialize Groq client for memory: {e}")

        self._memories: dict[str, list[str]] = self._load_storage()
        logger.success(f"TutorMemory initialized with {len(self._memories)} student profiles")

    def _load_storage(self) -> dict[str, list[str]]:
        """Load stored memories from JSON file."""
        if MEMORY_FILE_PATH.exists():
            try:
                with open(MEMORY_FILE_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load memory file ({e}); starting fresh.")
        return {}

    def _save_storage(self) -> None:
        """Persist memories to JSON file."""
        try:
            with open(MEMORY_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(self._memories, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to persist student memories: {e}")

    async def get_student_profile(self, user_id: str) -> str:
        """Retrieve the student's learning profile from long-term memory.

        Args:
            user_id: Unique identifier for the student.

        Returns:
            A formatted string summarising the student's past mistakes,
            strengths, and interests — or a default message for new students.
        """
        memories = self._memories.get(user_id, [])
        if not memories:
            logger.info("No prior memories found for user '{}'", user_id)
            return (
                "This is a new student. No prior history is available. "
                "Start by asking about their English level and interests."
            )

        profile = "\n".join(memories)
        logger.info(
            "Loaded {} memory points for user '{}'", len(memories), user_id
        )
        return profile

    async def extract_session_memories(
        self, messages: list[dict[str, str]], user_id: str
    ) -> None:
        """Extract and persist facts from the conversation into long-term memory.

        Uses Groq cloud API to extract key language corrections and student interests.

        Args:
            messages: The full conversation message list from the LLM context.
            user_id: Unique identifier for the student.
        """
        if not self._groq_client or len(messages) < 2:
            logger.info("Skipping memory extraction: insufficient conversation history.")
            return

        logger.info(
            "Extracting session memories ({} messages) for user '{}'",
            len(messages),
            user_id,
        )

        # Filter out system prompts to keep context clean
        chat_transcript = [
            f"{m.get('role', 'user').capitalize()}: {m.get('content', '')}"
            for m in messages
            if m.get("role") in ("user", "assistant") and m.get("content")
        ]

        if not chat_transcript:
            return

        transcript_text = "\n".join(chat_transcript[-10:])  # Last 10 turns

        extraction_prompt = (
            "You are an English language tutor analyzing a student conversation.\n"
            "Extract 2 to 4 concise bullet points summarizing:\n"
            "- English grammar/vocabulary/pronunciation mistakes made by the student and how to correct them\n"
            "- Topics and personal interests mentioned by the student\n"
            "- The student's estimated English level (e.g. Beginner, Intermediate, Advanced)\n\n"
            "Format requirements:\n"
            "- Return ONLY bullet points starting with '- '\n"
            "- Keep each bullet point under 20 words\n"
            "- Do not write intro or outro text\n\n"
            f"Conversation Transcript:\n{transcript_text}"
        )

        try:
            response = await asyncio.wait_for(
                self._groq_client.chat.completions.create(
                    model="groq/compound-mini",
                    messages=[{"role": "user", "content": extraction_prompt}],
                    temperature=0.2,
                    max_tokens=250,
                ),
                timeout=8.0,
            )

            raw_content = response.choices[0].message.content or ""
            new_bullets = [
                line.strip()
                for line in raw_content.splitlines()
                if line.strip().startswith("-")
            ]

            if new_bullets:
                existing = self._memories.get(user_id, [])
                # Keep up to 10 most recent memory bullets to avoid token bloat
                updated = (existing + new_bullets)[-10:]
                self._memories[user_id] = updated
                self._save_storage()
                logger.success(
                    "Persisted {} new memories for user '{}'",
                    len(new_bullets),
                    user_id,
                )
        except Exception as e:
            logger.warning(f"Memory extraction failed for '{user_id}': {e}")
