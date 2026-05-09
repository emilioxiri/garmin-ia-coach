"""Tests for garmin_coach.app.config."""

import dataclasses
from pathlib import Path

import pytest

from garmin_coach.app.config import load_settings

_REQUIRED_ENVS = {
    "GARMIN_EMAIL": "test@example.com",
    "GARMIN_PASSWORD": "secret",
    "TELEGRAM_BOT_TOKEN": "123:abc",
    "TELEGRAM_ALLOWED_USER_ID": "42",
    "GROQ_API_KEY": "gsk_test",
}


def _set_required(monkeypatch):
    for k, v in _REQUIRED_ENVS.items():
        monkeypatch.setenv(k, v)


def test_load_settings_reads_all_env_vars(monkeypatch):
    _set_required(monkeypatch)
    monkeypatch.setenv("SYNC_TIME_MORNING", "06:30")
    monkeypatch.setenv("SYNC_TIME_EVENING", "23:00")
    monkeypatch.setenv("DAYS_HISTORY", "60")
    monkeypatch.setenv("DB_PATH", "/tmp/test.json")
    monkeypatch.setenv("SESSION_PATH", "/tmp/session.json")
    monkeypatch.setenv("LOG_PATH", "/tmp/bot.log")
    monkeypatch.setenv("TIMEZONE", "UTC")
    monkeypatch.setenv("LLM_MODEL", "some-model")

    s = load_settings()

    assert s.garmin_email == "test@example.com"
    assert s.garmin_password == "secret"
    assert s.telegram_bot_token == "123:abc"
    assert s.telegram_allowed_user_id == 42
    assert s.groq_api_key == "gsk_test"
    assert s.sync_time_morning == "06:30"
    assert s.sync_time_evening == "23:00"
    assert s.days_history == 60
    assert s.db_path == Path("/tmp/test.json")
    assert s.session_path == Path("/tmp/session.json")
    assert s.log_path == Path("/tmp/bot.log")
    assert s.timezone == "UTC"
    assert s.llm_model == "some-model"


@pytest.mark.parametrize(
    "missing_var",
    ["GARMIN_EMAIL", "TELEGRAM_BOT_TOKEN", "GROQ_API_KEY", "TELEGRAM_ALLOWED_USER_ID"],
)
def test_load_settings_raises_when_required_missing(monkeypatch, missing_var):
    _set_required(monkeypatch)
    monkeypatch.delenv(missing_var, raising=False)

    with pytest.raises(RuntimeError, match="Missing required environment variables"):
        load_settings()


def test_load_settings_uses_defaults(monkeypatch):
    _set_required(monkeypatch)
    # Ensure optional env vars are not set
    for var in (
        "SYNC_TIME_MORNING",
        "SYNC_TIME_EVENING",
        "DAYS_HISTORY",
        "DB_PATH",
        "LOG_PATH",
    ):
        monkeypatch.delenv(var, raising=False)

    s = load_settings()

    assert s.db_path == Path("/data/garmin_coach.json")
    assert s.log_path == Path("/data/logs/bot.log")
    assert s.days_history == 30
    assert s.sync_time_morning == "07:00"
    assert s.sync_time_evening == "22:00"


def test_settings_is_frozen(monkeypatch):
    _set_required(monkeypatch)
    s = load_settings()

    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        s.garmin_email = "other@example.com"  # type: ignore[misc]
