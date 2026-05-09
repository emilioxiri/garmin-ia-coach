"""Tests for Scheduler: start/stop, morning/evening jobs."""

import threading
from pathlib import Path
from unittest.mock import MagicMock, patch


from garmin_coach.app.config import Settings
from garmin_coach.app.scheduler import Scheduler


def _make_settings(**overrides):
    defaults = dict(
        garmin_email="test@example.com",
        garmin_password="secret",
        telegram_bot_token="123:abc",
        telegram_allowed_user_id=42,
        groq_api_key="gsk_test",
        sync_time_morning="07:00",
        sync_time_evening="22:00",
        days_history=30,
        db_path=Path("/data/garmin_coach.json"),
        session_path=Path("/data/garmin_session.json"),
        log_path=Path("/data/logs/bot.log"),
    )
    defaults.update(overrides)
    return Settings(**defaults)


def _make_scheduler(**overrides):
    defaults = dict(
        sync_service=MagicMock(),
        briefing_service=MagicMock(),
        sync_log_repo=MagicMock(),
        bot_app=MagicMock(),
        settings=_make_settings(),
        check_interval_seconds=1,
    )
    defaults.update(overrides)
    return Scheduler(**defaults)


# ── start / stop ──────────────────────────────────────────────────────────────


def test_start_returns_daemon_thread():
    scheduler = _make_scheduler()
    with patch("schedule.every") as mock_every:
        mock_every.return_value.day.at.return_value.do.return_value = None
        thread = scheduler.start()
    assert isinstance(thread, threading.Thread)
    assert thread.daemon is True
    scheduler.stop()


def test_stop_signals_thread():
    scheduler = _make_scheduler()
    with patch("schedule.every") as mock_every:
        mock_every.return_value.day.at.return_value.do.return_value = None
        scheduler.start()
    assert not scheduler._stop_event.is_set()
    scheduler.stop()
    assert scheduler._stop_event.is_set()


def test_start_schedules_morning_and_evening():
    scheduler = _make_scheduler()
    with patch("schedule.every") as mock_every:
        day_mock = MagicMock()
        mock_every.return_value.day = day_mock
        at_mock = MagicMock()
        day_mock.at.return_value = at_mock
        at_mock.do.return_value = None
        scheduler.start()
        scheduler.stop()
    # .at() called twice (morning + evening)
    assert day_mock.at.call_count == 2
    at_calls = [c[0][0] for c in day_mock.at.call_args_list]
    assert "07:00" in at_calls
    assert "22:00" in at_calls


# ── _run_job ──────────────────────────────────────────────────────────────────


def test_run_job_calls_sync_service():
    sync_mock = MagicMock()
    briefing_mock = MagicMock()
    briefing_mock.generate.return_value = "Briefing text"

    bot_app_mock = MagicMock()
    bot_app_mock.loop = None  # no loop → briefing skipped

    scheduler = _make_scheduler(
        sync_service=sync_mock,
        briefing_service=briefing_mock,
        bot_app=bot_app_mock,
    )
    scheduler._run_job("morning")
    sync_mock.run.assert_called_once()


def test_run_job_calls_briefing_service():
    sync_mock = MagicMock()
    briefing_mock = MagicMock()
    briefing_mock.generate.return_value = "Briefing"

    bot_app_mock = MagicMock()
    bot_app_mock.loop = None

    scheduler = _make_scheduler(
        sync_service=sync_mock,
        briefing_service=briefing_mock,
        bot_app=bot_app_mock,
    )
    scheduler._run_job("evening")
    briefing_mock.generate.assert_called_once_with("evening")


def test_run_job_sends_briefing_via_loop():
    sync_mock = MagicMock()
    briefing_mock = MagicMock()
    briefing_mock.generate.return_value = "Briefing"

    loop_mock = MagicMock()
    loop_mock.is_running.return_value = True

    bot_app_mock = MagicMock()
    bot_app_mock.loop = loop_mock

    scheduler = _make_scheduler(
        sync_service=sync_mock,
        briefing_service=briefing_mock,
        bot_app=bot_app_mock,
    )

    with patch("asyncio.run_coroutine_threadsafe") as mock_run:
        scheduler._run_job("morning")
        mock_run.assert_called_once()


def test_run_job_sync_error_does_not_prevent_briefing():
    sync_mock = MagicMock()
    sync_mock.run.side_effect = RuntimeError("network error")
    briefing_mock = MagicMock()
    briefing_mock.generate.return_value = "Briefing"
    bot_app_mock = MagicMock()
    bot_app_mock.loop = None

    scheduler = _make_scheduler(
        sync_service=sync_mock,
        briefing_service=briefing_mock,
        bot_app=bot_app_mock,
    )
    # Should not raise
    scheduler._run_job("morning")
    briefing_mock.generate.assert_called_once()


def test_morning_job_uses_morning_moment():
    scheduler = _make_scheduler()
    with patch.object(scheduler, "_run_job") as mock_run:
        scheduler._morning_job()
        mock_run.assert_called_once_with("morning")


def test_evening_job_uses_evening_moment():
    scheduler = _make_scheduler()
    with patch.object(scheduler, "_run_job") as mock_run:
        scheduler._evening_job()
        mock_run.assert_called_once_with("evening")
