"""System prompt generation for the English tutor."""


def generate_tutor_system_prompt(student_profile: str) -> str:
    """Build the tutor system prompt with the student's memory profile.

    Args:
        student_profile: A summary of the student's past mistakes,
            strengths, and interests retrieved from long-term memory.

    Returns:
        The fully interpolated system prompt string.
    """
    return (
        "You are an expert, friendly English tutor. Engage in natural spoken conversation. "
        "Keep replies concise (1-3 sentences).\n\n"
        f"STUDENT PROFILE:\n{student_profile}\n\n"
        "GUIDELINES:\n"
        "- If the student makes a grammar error: briefly state the correction, then continue.\n"
        "- If correct: reply naturally with a relevant conversational follow-up."
    )
