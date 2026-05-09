"""Tests for services/coach_service.py — CoachService facade."""

from unittest.mock import MagicMock

from garmin_coach.services.coach_service import CoachService
from garmin_coach.services.session_manager import SessionManager


def _make_session(response="ok"):
    s = MagicMock()
    s.chat.return_value = response
    s.history = []
    return s


def _make_service(session=None):
    fixed_session = session or _make_session()
    manager = SessionManager(lambda: fixed_session)
    return CoachService(manager), fixed_session


def test_chat_delegates_to_session():
    service, session = _make_service(_make_session("¡Buen entreno!"))
    result = service.chat(user_id=42, message="hola")
    session.chat.assert_called_once_with("hola")
    assert result == "¡Buen entreno!"


def test_chat_different_users_use_different_sessions():
    from garmin_coach.services.session_manager import SessionManager

    manager = SessionManager(_make_session)
    service = CoachService(manager)
    service.chat(1, "msg1")
    service.chat(2, "msg2")
    s1 = manager.get_or_create(1)
    s2 = manager.get_or_create(2)
    assert s1 is not s2


def test_reset_delegates_to_manager():
    manager = MagicMock(spec=SessionManager)
    service = CoachService(manager)
    service.reset(user_id=7)
    manager.reset.assert_called_once_with(7)


def test_get_session_returns_session():
    service, session = _make_service()
    result = service.get_session(user_id=42)
    assert result is session
