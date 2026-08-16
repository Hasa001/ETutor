"""Tests for the TutorMemory long-term memory layer."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src/ to path so we can import project modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from memory import TutorMemory
from config import TutorConfig


@pytest.fixture
def mock_config() -> TutorConfig:
    """Create a TutorConfig with test values."""
    return TutorConfig(
        GROQ_API_KEY="test_key_123",
        QDRANT_PATH="./test_qdrant",
    )


@patch("memory.Memory.from_config")
def test_get_student_profile_with_memories(
    mock_from_config: MagicMock, mock_config: TutorConfig
) -> None:
    """Profile should format existing memories as bullet points."""
    mock_mem = MagicMock()
    mock_mem.search.return_value = {
        "results": [
            {"memory": "Student confuses 'their' and 'there'"},
            {"memory": "Student is interested in science fiction"},
        ]
    }
    mock_from_config.return_value = mock_mem

    tutor_mem = TutorMemory(mock_config)
    profile = tutor_mem.get_student_profile("student_1")

    assert "their" in profile
    assert "science fiction" in profile
    assert profile.startswith("- ")
    mock_mem.search.assert_called_once_with(
        query="What does the student struggle with in English? What are their interests?",
        filters={"user_id": "student_1"},
        top_k=10,
    )


@patch("memory.Memory.from_config")
def test_get_student_profile_new_student(
    mock_from_config: MagicMock, mock_config: TutorConfig
) -> None:
    """Profile should return default message for new students."""
    mock_mem = MagicMock()
    mock_mem.search.return_value = {"results": []}
    mock_from_config.return_value = mock_mem

    tutor_mem = TutorMemory(mock_config)
    profile = tutor_mem.get_student_profile("new_student")

    assert "new student" in profile.lower()
    assert "No prior history" in profile
