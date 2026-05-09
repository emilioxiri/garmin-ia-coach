"""
services/session_manager.py
SessionManager: creates and caches CoachSession instances per user_id.
"""

from __future__ import annotations

from typing import Callable

from garmin_coach.services.coach_session import CoachSession


class SessionManager:
    """Holds one CoachSession per user_id; creates on first access."""

    def __init__(self, session_factory: Callable[[], CoachSession]) -> None:
        self._factory = session_factory
        self._sessions: dict[int, CoachSession] = {}

    def get_or_create(self, user_id: int) -> CoachSession:
        if user_id not in self._sessions:
            self._sessions[user_id] = self._factory()
        return self._sessions[user_id]

    def reset(self, user_id: int) -> None:
        session = self._sessions.get(user_id)
        if session is not None:
            session.reset()

    def remove(self, user_id: int) -> None:
        self._sessions.pop(user_id, None)
