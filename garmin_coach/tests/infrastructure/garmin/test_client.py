"""Tests for GarminClient."""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock, patch


from garmin_coach.infrastructure.garmin.client import GarminClient
from garmin_coach.infrastructure.garmin.mfa_handler import MFAHandler


def _make_settings(tmp_path: Path) -> MagicMock:
    settings = MagicMock()
    settings.garmin_email = "user@example.com"
    settings.garmin_password = "secret"
    settings.session_path = tmp_path / "session.json"
    return settings


def test_authenticate_reuses_cached_client(tmp_path):
    settings = _make_settings(tmp_path)
    mfa = MFAHandler()
    client = GarminClient(settings, mfa)

    mock_garmin = MagicMock()

    with patch(
        "garmin_coach.infrastructure.garmin.client.Garmin", return_value=mock_garmin
    ):
        first = client.authenticate()
        second = client.authenticate()

    assert first is second
    # login should only have been called once
    mock_garmin.login.assert_called_once()


def test_authenticate_full_login_when_no_session(tmp_path):
    settings = _make_settings(tmp_path)
    mfa = MFAHandler()
    client = GarminClient(settings, mfa)

    mock_garmin = MagicMock()
    mock_garmin.login.return_value = None
    mock_garmin.client.dump.return_value = None

    with patch(
        "garmin_coach.infrastructure.garmin.client.Garmin", return_value=mock_garmin
    ):
        result = client.authenticate()

    mock_garmin.login.assert_called_once_with()
    mock_garmin.client.dump.assert_called_once_with(str(settings.session_path))
    assert result is mock_garmin


def test_authenticate_reuses_session_from_disk(tmp_path):
    settings = _make_settings(tmp_path)
    settings.session_path.write_text("{}")
    mfa = MFAHandler()
    client = GarminClient(settings, mfa)

    mock_garmin = MagicMock()
    mock_garmin.login.return_value = None

    with patch(
        "garmin_coach.infrastructure.garmin.client.Garmin", return_value=mock_garmin
    ):
        result = client.authenticate()

    mock_garmin.login.assert_called_once_with(tokenstore=str(settings.session_path))
    assert result is mock_garmin


def test_authenticate_falls_back_to_full_login_when_session_expired(tmp_path):
    settings = _make_settings(tmp_path)
    settings.session_path.write_text("{}")
    mfa = MFAHandler()
    client = GarminClient(settings, mfa)

    mock_garmin = MagicMock()
    mock_garmin.login.side_effect = [Exception("expired"), None]
    mock_garmin.client.dump.return_value = None

    with patch(
        "garmin_coach.infrastructure.garmin.client.Garmin", return_value=mock_garmin
    ):
        client.authenticate()

    assert mock_garmin.login.call_count == 2
    assert not settings.session_path.exists()


def test_authenticate_mfa_flow(tmp_path):
    """Simulate a login that requires MFA: the handler receives notify and provide_code unblocks."""
    settings = _make_settings(tmp_path)
    mfa = MFAHandler(timeout_seconds=5)
    notifications: list[str] = []
    mfa.set_notifier(notifications.append)

    client = GarminClient(settings, mfa)

    mock_garmin = MagicMock()
    captured_prompt_fn: list = []

    # Synchronization: fires when login is about to call prompt_mfa
    login_started = threading.Event()

    def _capture_init(email, password, prompt_mfa=None):
        captured_prompt_fn.append(prompt_mfa)
        return mock_garmin

    def _login_needs_mfa():
        # Signal that we are about to block on prompt_mfa
        login_started.set()
        # Simulate garminconnect calling prompt_mfa (blocks until code provided)
        code = captured_prompt_fn[0]()
        mock_garmin._mfa_code = code

    mock_garmin.login.side_effect = _login_needs_mfa
    mock_garmin.client.dump.return_value = None

    def _provide_code():
        # Wait until login is blocking on prompt_mfa before providing code
        login_started.wait(timeout=5)
        mfa.provide_code("654321")

    t = threading.Thread(target=_provide_code)
    t.start()

    with patch(
        "garmin_coach.infrastructure.garmin.client.Garmin", side_effect=_capture_init
    ):
        result = client.authenticate()

    t.join()

    assert result is mock_garmin
    assert mock_garmin._mfa_code == "654321"
    assert len(notifications) == 1


def test_reset_clears_cache_and_deletes_session(tmp_path):
    settings = _make_settings(tmp_path)
    settings.session_path.write_text("{}")
    mfa = MFAHandler()
    client = GarminClient(settings, mfa)

    mock_garmin = MagicMock()
    mock_garmin.login.return_value = None

    with patch(
        "garmin_coach.infrastructure.garmin.client.Garmin", return_value=mock_garmin
    ):
        client.authenticate()

    assert client._client is not None
    client.reset()

    assert client._client is None
    assert not settings.session_path.exists()
