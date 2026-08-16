"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class TutorConfig(BaseSettings):
    """Validated configuration for the English Tutor AI.

    Reads values from a `.env` file and environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    GROQ_API_KEY: str
    AUDIO_IN_SAMPLE_RATE: int = 16_000
    AUDIO_OUT_SAMPLE_RATE: int = 24_000
    VAD_STOP_SECS: float = 0.4
    VAD_START_SECS: float = 0.25
    VAD_CONFIDENCE: float = 0.8
    VAD_MIN_VOLUME: float = 0.6
    # Seconds to suppress mic audio after bot stops speaking.
    # Covers acoustic reverb tail & speaker → mic propagation delay.
    VAD_HOLDOFF_SECS: float = 0.8
    USER_ID: str = "default_student_1"
    QDRANT_PATH: str = "./qdrant_storage"
