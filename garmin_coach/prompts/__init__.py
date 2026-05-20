"""
prompts/
Prompt resources loaded from disk. CoachSession will use read_system_prompt()
in Phase 3 instead of the inline SYSTEM_PROMPT string in coach.py.
"""

from pathlib import Path


def read_system_prompt() -> str:
    """Return the coach system prompt text from coach_system.md."""
    return (Path(__file__).parent / "coach_system.md").read_text(encoding="utf-8")
