"""Tests for configuration validation and prompt generation."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

# Add src/ to path so we can import project modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import TutorConfig
from prompts import generate_tutor_system_prompt


class TestTutorConfig:
    """Configuration validation tests."""

    def test_missing_groq_api_key_raises(self) -> None:
        """TutorConfig must raise ValidationError when GROQ_API_KEY is absent."""
        # Clear any environment variable that might satisfy the requirement
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValidationError):
                TutorConfig(
                    _env_file=None,  # Prevent reading .env file
                )

    def test_valid_config_with_key(self) -> None:
        """TutorConfig should accept a valid GROQ_API_KEY."""
        cfg = TutorConfig(GROQ_API_KEY="gsk_test_key_12345")
        assert cfg.GROQ_API_KEY == "gsk_test_key_12345"
        assert cfg.AUDIO_IN_SAMPLE_RATE == 16_000
        assert cfg.AUDIO_OUT_SAMPLE_RATE == 24_000
        assert cfg.VAD_STOP_SECS == 0.4
        assert cfg.USER_ID == "default_student_1"


class TestSystemPrompt:
    """System prompt generation tests."""

    def test_prompt_includes_student_profile(self) -> None:
        """The system prompt must contain the interpolated student profile."""
        profile = "- Struggles with articles\n- Interested in cooking"
        prompt = generate_tutor_system_prompt(profile)

        assert "Struggles with articles" in prompt
        assert "Interested in cooking" in prompt
        assert "STUDENT PROFILE" in prompt
        assert "RULES FOR CORRECTION" in prompt

    def test_prompt_includes_new_student_default(self) -> None:
        """The prompt should work with the default 'new student' profile."""
        default = (
            "This is a new student. No prior history is available. "
            "Start by asking about their English level and interests."
        )
        prompt = generate_tutor_system_prompt(default)

        assert "new student" in prompt
        assert "English level" in prompt
