"""Tests for services/session_manager.py — SessionManager."""

from unittest.mock import MagicMock

from garmin_coach.services.session_manager import SessionManager


def _make_session():
    s = MagicMock()
    s.history = []
    return s


def test_get_or_create_creates_on_first_call():
    created = []

    def factory():
        s = _make_session()
        created.append(s)
        return s

    mgr = SessionManager(factory)
    session = mgr.get_or_create(user_id=1)
    assert len(created) == 1
    assert session is created[0]


def test_get_or_create_reuses_existing_session():
    call_count = [0]

    def factory():
        call_count[0] += 1
        return _make_session()

    mgr = SessionManager(factory)
    s1 = mgr.get_or_create(1)
    s2 = mgr.get_or_create(1)
    assert s1 is s2
    assert call_count[0] == 1


def test_get_or_create_different_users_get_different_sessions():
    mgr = SessionManager(_make_session)
    s1 = mgr.get_or_create(1)
    s2 = mgr.get_or_create(2)
    assert s1 is not s2


def test_reset_calls_session_reset():
    session = _make_session()
    mgr = SessionManager(lambda: session)
    mgr.get_or_create(1)
    mgr.reset(1)
    session.reset.assert_called_once()


def test_reset_nonexistent_user_is_noop():
    mgr = SessionManager(_make_session)
    mgr.reset(999)  # should not raise


def test_remove_drops_session():
    call_count = [0]

    def factory():
        call_count[0] += 1
        return _make_session()

    mgr = SessionManager(factory)
    mgr.get_or_create(1)
    mgr.remove(1)
    mgr.get_or_create(1)
    assert call_count[0] == 2


def test_remove_nonexistent_user_is_noop():
    mgr = SessionManager(_make_session)
    mgr.remove(999)  # should not raise
