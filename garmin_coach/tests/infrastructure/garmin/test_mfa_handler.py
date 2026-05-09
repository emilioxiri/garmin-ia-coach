"""Tests for MFAHandler."""

from __future__ import annotations

import threading

import pytest

from garmin_coach.infrastructure.garmin.mfa_handler import MFAHandler


def test_provide_code_releases_wait_for_code():
    handler = MFAHandler(timeout_seconds=5)

    def _provide():
        handler.provide_code("123456")

    t = threading.Thread(target=_provide)
    t.start()
    code = handler.wait_for_code()
    t.join()
    assert code == "123456"


def test_wait_for_code_raises_on_timeout():
    handler = MFAHandler(timeout_seconds=0)
    with pytest.raises(TimeoutError):
        handler.wait_for_code()


def test_notify_user_without_notifier_does_not_raise():
    handler = MFAHandler()
    handler.notify_user("test message")  # should not raise


def test_notify_user_with_notifier_calls_callback():
    handler = MFAHandler()
    received: list[str] = []
    handler.set_notifier(received.append)
    handler.notify_user("hello")
    assert received == ["hello"]


def test_clear_resets_event_and_code():
    handler = MFAHandler(timeout_seconds=5)
    handler._code = "stale"
    handler._event.set()

    handler.clear()

    assert handler._code is None
    assert not handler._event.is_set()


def test_wait_for_code_clears_state_after_consuming():
    handler = MFAHandler(timeout_seconds=5)

    def _provide():
        handler.provide_code("abc")

    t = threading.Thread(target=_provide)
    t.start()
    handler.wait_for_code()
    t.join()

    assert handler._code is None
    assert not handler._event.is_set()


def test_notifier_exception_does_not_propagate():
    handler = MFAHandler()

    def _bad_notifier(msg: str) -> None:
        raise RuntimeError("notifier crashed")

    handler.set_notifier(_bad_notifier)
    handler.notify_user("trigger")  # must not raise
