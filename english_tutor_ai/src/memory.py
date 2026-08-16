import asyncio
import os
from typing import Any

from loguru import logger

# Disable anonymous Mem0 PostHog telemetry to prevent duplicate client logs
os.environ["MEM0_TELEMETRY"] = "False"

from mem0 import Memory  # PyPI package is 'mem0ai', but module is 'mem0'

from config import TutorConfig


class TutorMemory:
    """Wraps Mem0 for student-specific long-term memory.

    Uses Groq as the LLM for fact extraction, HuggingFace for local
    embeddings, and a local Qdrant instance for vector storage.
    """

    def __init__(self, config: TutorConfig) -> None:
        if config.GROQ_API_KEY:
            os.environ["GROQ_API_KEY"] = config.GROQ_API_KEY

        mem0_config: dict[str, Any] = {
            "llm": {
                "provider": "groq",
                "config": {
                    "model": "llama-3.1-8b-instant",
                    "api_key": config.GROQ_API_KEY,
                    "temperature": 0.1,
                    "max_tokens": 400,
                },
            },
            "embedder": {
                "provider": "fastembed",
                "config": {
                    "model": "sentence-transformers/all-MiniLM-L6-v2",
                    "embedding_dims": 384,
                },
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "path": config.QDRANT_PATH,
                    "embedding_model_dims": 384,  # CRITICAL: matches MiniLM-L6-v2
                },
            },
            "version": "v1.1",
        }

        logger.info("Initializing Mem0 with local Qdrant at '{}'", config.QDRANT_PATH)
        try:
            self.memory: Memory = Memory.from_config(config_dict=mem0_config)
            logger.success("Mem0 memory engine ready")
        except Exception as e:
            logger.error(f"Mem0 initialization failed ({e}). Memory will operate in fallback mode.")
            self.memory = None  # type: ignore

    async def get_student_profile(self, user_id: str) -> str:
        """Retrieve the student's learning profile from long-term memory.

        Args:
            user_id: Unique identifier for the student.

        Returns:
            A formatted string summarising the student's past mistakes,
            strengths, and interests — or a default message for new students.
        """
        if self.memory is None:
            logger.info("Memory engine not initialized; treating as new student '{}'", user_id)
            return (
                "This is a new student. No prior history is available. "
                "Start by asking about their English level and interests."
            )

        query = (
            "What does the student struggle with in English? "
            "What are their interests?"
        )
        try:
            loop = asyncio.get_running_loop()
            results = await loop.run_in_executor(
                None,
                lambda: self.memory.search(
                    query=query,
                    filters={"user_id": user_id},
                    top_k=10,
                )
            )
            memories = results.get("results", [])
        except Exception:
            logger.opt(exception=True).warning(
                "Memory search failed for user '{}'; treating as new student",
                user_id,
            )
            memories = []

        if not memories:
            logger.info("No prior memories found for user '{}'", user_id)
            return (
                "This is a new student. No prior history is available. "
                "Start by asking about their English level and interests."
            )

        profile_lines: list[str] = [
            f"- {mem['memory']}" for mem in memories if "memory" in mem
        ]
        profile = "\n".join(profile_lines)
        logger.info(
            "Loaded {} memories for user '{}'", len(profile_lines), user_id
        )
        return profile

    async def extract_session_memories(
        self, messages: list[dict[str, str]], user_id: str
    ) -> None:
        """Extract and persist facts from the conversation into long-term memory.

        Runs the blocking Mem0 `.add()` call inside a threadpool executor
        so it does not block the async event loop.

        Args:
            messages: The full conversation message list from the LLM context.
            user_id: Unique identifier for the student.
        """
        if self.memory is None:
            logger.warning("Memory engine not initialized; skipping memory persistence for '{}'", user_id)
            return

        logger.info(
            "Extracting session memories ({} messages) for user '{}'",
            len(messages),
            user_id,
        )
        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: self.memory.add(messages=messages, user_id=user_id),
            )
            added = [
                r for r in result.get("results", []) if r.get("event") == "ADD"
            ]
            logger.success(
                "Persisted {} new memories for user '{}'",
                len(added),
                user_id,
            )
        except Exception:
            logger.opt(exception=True).error(
                "Failed to extract session memories for user '{}'", user_id
            )
