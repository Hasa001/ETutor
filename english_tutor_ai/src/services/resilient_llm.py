"""Resilient Groq LLM Service with automatic model fallback and token optimization."""

from typing import Sequence
import openai
from loguru import logger
from openai import RateLimitError, APIStatusError
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.services.groq.llm import GroqLLMService


class ResilientGroqLLMService(GroqLLMService):
    """Extends GroqLLMService with automated multi-model fallback on 429 rate limits.

    When the primary model (e.g. llama-3.3-70b-versatile) reaches its token-per-day
    or requests-per-minute quota, this service automatically cascades to fallback
    models (e.g. llama-3.1-8b-instant, gemma2-9b-it) without dropping the user's turn.
    """

    def __init__(
        self,
        *,
        api_key: str,
        primary_model: str = "llama-3.3-70b-versatile",
        fallback_models: Sequence[str] = (
            "llama-3.1-8b-instant",
            "gemma2-9b-it",
        ),
        max_tokens: int = 250,
        **kwargs,
    ):
        settings = GroqLLMService.Settings(
            model=primary_model,
            max_tokens=max_tokens,
            temperature=0.7,
        )
        super().__init__(api_key=api_key, settings=settings, **kwargs)

        self._primary_model = primary_model
        self._fallback_models = list(fallback_models)
        self._active_model = primary_model
        self._max_tokens = max_tokens

    async def get_chat_completions(self, context: LLMContext):
        """Execute chat completion with automatic model fallback on HTTP 429 or rate limits."""
        adapter = self.get_llm_adapter()
        params_from_context = adapter.get_llm_invocation_params(
            context,
            system_instruction=self._settings.system_instruction,
            convert_developer_to_user=not self.supports_developer_role,
        )
        params = self.build_chat_completion_params(params_from_context)
        params["max_tokens"] = self._max_tokens

        # Models to try: current active model first, then remaining fallback candidates
        candidate_models = [self._active_model] + [
            m for m in [self._primary_model] + self._fallback_models if m != self._active_model
        ]

        last_error = None
        for model_name in candidate_models:
            params["model"] = model_name
            try:
                logger.debug(f"Attempting LLM completion using model '{model_name}'...")
                chunks = await self._client.chat.completions.create(**params)
                
                # If we successfully switched to a fallback, update active model
                if model_name != self._active_model:
                    logger.success(f"Switched active LLM model to '{model_name}'")
                    self._active_model = model_name
                    self._settings.model = model_name
                
                return chunks

            except (RateLimitError, APIStatusError) as e:
                status_code = getattr(e, "status_code", None)
                is_rate_limit = isinstance(e, RateLimitError) or status_code == 429
                
                if is_rate_limit:
                    logger.warning(
                        f"Model '{model_name}' reached rate limit (429). Attempting fallback..."
                    )
                    last_error = e
                    continue
                else:
                    logger.error(f"Non-rate-limit error on model '{model_name}': {e}")
                    raise e
            except Exception as e:
                logger.warning(f"Error on model '{model_name}': {e}. Trying fallback...")
                last_error = e
                continue

        # If all candidates exhausted, raise the last encountered error
        logger.error("All LLM candidate models failed or hit rate limits.")
        if last_error:
            raise last_error
        raise RuntimeError("No candidate LLM models available.")
