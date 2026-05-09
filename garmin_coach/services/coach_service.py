"""
services/coach_service.py
CoachService: public facade for chat and reset operations.
Delegates session management to SessionManager.
"""

from __future__ import annotations

from garmin_coach.services.session_manager import SessionManager


class CoachService:
    """Facade used by the Telegram bot: chat(user_id, msg) and reset(user_id)."""

    def __init__(self, session_manager: SessionManager) -> None:
        self._manager = session_manager

    def chat(self, user_id: int, message: str) -> str:
        session = self._manager.get_or_create(user_id)
        return session.chat(message)

    def reset(self, user_id: int) -> None:
        self._manager.reset(user_id)

    def get_session(self, user_id: int):
        """Return (and create if needed) the CoachSession for user_id."""
        return self._manager.get_or_create(user_id)
