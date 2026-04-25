"""Unit tests for garmin_sync.py — all functions."""

import pytest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from tinydb import TinyDB
from tinydb.storages import MemoryStorage


def make_db():
    return TinyDB(storage=MemoryStorage)


def make_mock_client(activities=None):
    client = MagicMock()
    client.get_activities_by_date.return_value = activities or []
    client.get_activity.side_effect = Exception("no details")
    client.get_sleep_data.return_value = {}
    client.get_hrv_data.return_value = {}
    client.get_body_battery.return_value = []
    return client


# ── date window ───────────────────────────────────────────────────────────────

def test_sync_uses_30_days_when_db_empty():
    from garmin_coach.garmin_sync import sync_all

    db_inst = make_db()
    mock_client = make_mock_client()

    with (
        patch("garmin_coach.garmin_sync.get_garmin_client", return_value=mock_client),
        patch("garmin_coach.garmin_sync.get_db", return_value=db_inst),
        patch("garmin_coach.db._db_instance", db_inst),
    ):
        sync_all("email", "pass", days=30)

    expected_start = (date.today() - timedelta(days=30)).isoformat()
    expected_end = date.today().isoformat()
    mock_client.get_activities_by_date.assert_called_once_with(expected_start, expected_end)


def test_sync_uses_last_db_date_when_not_empty():
    from garmin_coach.garmin_sync import sync_all

    db_inst = make_db()
    last_date = (date.today() - timedelta(days=5)).isoformat()
    db_inst.table("sleep").insert({"date": last_date})

    mock_client = make_mock_client()

    with (
        patch("garmin_coach.garmin_sync.get_garmin_client", return_value=mock_client),
        patch("garmin_coach.garmin_sync.get_db", return_value=db_inst),
        patch("garmin_coach.db._db_instance", db_inst),
    ):
        sync_all("email", "pass", days=30)

    expected_end = date.today().isoformat()
    mock_client.get_activities_by_date.assert_called_once_with(last_date, expected_end)


def test_sync_calls_purge_before_fetching():
    from garmin_coach.garmin_sync import sync_all

    db_inst = make_db()
    mock_client = make_mock_client()
    call_order = []

    def fake_purge(days=30):
        call_order.append("purge")
        return {"activities": 0, "sleep": 0, "hrv": 0, "body_battery": 0}

    def fake_get_activities(*args, **kwargs):
        call_order.append("fetch")
        return []

    mock_client.get_activities_by_date.side_effect = fake_get_activities

    with (
        patch("garmin_coach.garmin_sync.get_garmin_client", return_value=mock_client),
        patch("garmin_coach.garmin_sync.get_db", return_value=db_inst),
        patch("garmin_coach.db._db_instance", db_inst),
        patch("garmin_coach.db.purge_old_data", side_effect=fake_purge),
    ):
        sync_all("email", "pass", days=30)

    assert call_order.index("purge") < call_order.index("fetch")


# ── activity storage ──────────────────────────────────────────────────────────

def test_sync_stores_all_activity_fields_from_api():
    from garmin_coach.garmin_sync import sync_all

    db_inst = make_db()
    activity = {
        "activityId": 12345,
        "activityName": "Morning Run",
        "startTimeLocal": date.today().isoformat() + " 07:00:00",
        "distance": 10000.0,
        "averageHR": 145,
        "verticalOscillation": 8.5,
        "groundContactTime": 245,
        "strideLength": 120,
        "avgRunCadence": 170,
        "trainingStressScore": 55.2,
    }
    mock_client = make_mock_client(activities=[activity])

    with (
        patch("garmin_coach.garmin_sync.get_garmin_client", return_value=mock_client),
        patch("garmin_coach.garmin_sync.get_db", return_value=db_inst),
        patch("garmin_coach.db._db_instance", db_inst),
    ):
        sync_all("email", "pass", days=30)

    stored = db_inst.table("activities").all()
    assert len(stored) == 1
    record = stored[0]
    assert record["verticalOscillation"] == 8.5
    assert record["groundContactTime"] == 245
    assert record["strideLength"] == 120
    assert record["avgRunCadence"] == 170
    assert record["trainingStressScore"] == 55.2
    assert record["averageHR"] == 145


def test_sync_merges_detailed_activity_metrics():
    from garmin_coach.garmin_sync import sync_all

    db_inst = make_db()
    activity = {
        "activityId": 99,
        "activityName": "Bike",
        "startTimeLocal": date.today().isoformat() + " 09:00:00",
        "verticalOscillation": None,
    }
    details = {
        "activityId": 99,
        "normPower": 220,
        "intensityFactor": 0.85,
        "summaryDTO": {
            "verticalOscillation": 8.5,
            "groundContactTime": 245,
        },
    }
    mock_client = make_mock_client(activities=[activity])
    mock_client.get_activity.side_effect = None
    mock_client.get_activity.return_value = details

    with (
        patch("garmin_coach.garmin_sync.get_garmin_client", return_value=mock_client),
        patch("garmin_coach.garmin_sync.get_db", return_value=db_inst),
        patch("garmin_coach.db._db_instance", db_inst),
    ):
        sync_all("email", "pass", days=30)

    stored = db_inst.table("activities").all()
    assert stored[0]["normPower"] == 220
    assert stored[0]["intensityFactor"] == 0.85
    # summaryDTO fields flattened and null overwritten
    assert stored[0]["verticalOscillation"] == 8.5
    assert stored[0]["groundContactTime"] == 245


def test_sync_continues_when_activity_details_fail():
    from garmin_coach.garmin_sync import sync_all

    db_inst = make_db()
    activity = {
        "activityId": 42,
        "activityName": "Run",
        "startTimeLocal": date.today().isoformat() + " 06:00:00",
    }
    mock_client = make_mock_client(activities=[activity])
    mock_client.get_activity.side_effect = Exception("API error")

    with (
        patch("garmin_coach.garmin_sync.get_garmin_client", return_value=mock_client),
        patch("garmin_coach.garmin_sync.get_db", return_value=db_inst),
        patch("garmin_coach.db._db_instance", db_inst),
    ):
        result = sync_all("email", "pass", days=30)

    assert result["activities"] == 1


# ── summary ───────────────────────────────────────────────────────────────────

def test_sync_summary_includes_purged():
    from garmin_coach.garmin_sync import sync_all

    db_inst = make_db()
    mock_client = make_mock_client()

    with (
        patch("garmin_coach.garmin_sync.get_garmin_client", return_value=mock_client),
        patch("garmin_coach.garmin_sync.get_db", return_value=db_inst),
        patch("garmin_coach.db._db_instance", db_inst),
    ):
        result = sync_all("email", "pass", days=30)

    assert "purged" in result


def test_sync_stores_sleep_records():
    from garmin_coach.garmin_sync import sync_all

    db_inst = make_db()
    mock_client = make_mock_client()
    mock_client.get_sleep_data.return_value = {
        "dailySleepDTO": {
            "sleepTimeSeconds": 28800,
            "deepSleepSeconds": 7200,
            "lightSleepSeconds": 14400,
            "remSleepSeconds": 5400,
            "awakeSleepSeconds": 1800,
            "sleepScores": {"overall": {"value": 82}},
            "restingHeartRate": 48,
        }
    }

    with (
        patch("garmin_coach.garmin_sync.get_garmin_client", return_value=mock_client),
        patch("garmin_coach.garmin_sync.get_db", return_value=db_inst),
        patch("garmin_coach.db._db_instance", db_inst),
    ):
        result = sync_all("email", "pass", days=1)

    assert result["sleep"] >= 1
    sleep_records = db_inst.table("sleep").all()
    assert len(sleep_records) >= 1
    assert sleep_records[0]["duration_s"] == 28800
    assert sleep_records[0]["score"] == 82


def test_sync_stores_hrv_records():
    from garmin_coach.garmin_sync import sync_all

    db_inst = make_db()
    mock_client = make_mock_client()
    mock_client.get_hrv_data.return_value = {
        "hrvSummary": {
            "weeklyAvg": 55,
            "lastNight": 52,
            "lastNight5MinHigh": 70,
            "status": "BALANCED",
            "feedbackPhrase": "HRV_BALANCED_1",
        }
    }

    with (
        patch("garmin_coach.garmin_sync.get_garmin_client", return_value=mock_client),
        patch("garmin_coach.garmin_sync.get_db", return_value=db_inst),
        patch("garmin_coach.db._db_instance", db_inst),
    ):
        result = sync_all("email", "pass", days=1)

    assert result["hrv"] >= 1
    hrv_records = db_inst.table("hrv").all()
    assert hrv_records[0]["weeklyAvg"] == 55
    assert hrv_records[0]["status"] == "BALANCED"


def test_sync_stores_body_battery_records():
    from garmin_coach.garmin_sync import sync_all

    db_inst = make_db()
    mock_client = make_mock_client()
    mock_client.get_body_battery.return_value = [
        {"bodyBatteryValuesArray": [[0, 80], [1, 45], [2, 90]]}
    ]

    with (
        patch("garmin_coach.garmin_sync.get_garmin_client", return_value=mock_client),
        patch("garmin_coach.garmin_sync.get_db", return_value=db_inst),
        patch("garmin_coach.db._db_instance", db_inst),
    ):
        result = sync_all("email", "pass", days=1)

    assert result["body_battery"] >= 1
    bb_records = db_inst.table("body_battery").all()
    assert bb_records[0]["max"] == 90
    assert bb_records[0]["min"] == 45


# ── get_garmin_client ─────────────────────────────────────────────────────────

def test_get_garmin_client_reuses_session_when_exists(tmp_path):
    import garmin_coach.garmin_sync as garmin_sync

    session_path = tmp_path / "session.json"
    session_path.write_text("{}")  # file must exist for .exists() to return True

    mock_client = MagicMock()
    mock_client.login.return_value = None

    with (
        patch("garmin_coach.garmin_sync.Garmin", return_value=mock_client),
        patch("garmin_coach.garmin_sync.SESSION_PATH", session_path),
    ):
        result = garmin_sync.get_garmin_client("email", "pass")

    mock_client.login.assert_called_once_with(tokenstore=str(session_path))
    assert result is mock_client


def test_get_garmin_client_full_login_when_no_session(tmp_path):
    import garmin_coach.garmin_sync as garmin_sync

    session_path = tmp_path / "session.json"
    mock_client = MagicMock()
    mock_client.login.return_value = None
    mock_client.client.dump.return_value = None

    with (
        patch("garmin_coach.garmin_sync.Garmin", return_value=mock_client),
        patch("garmin_coach.garmin_sync.SESSION_PATH", session_path),
    ):
        result = garmin_sync.get_garmin_client("email", "pass")

    mock_client.login.assert_called_once_with()
    mock_client.client.dump.assert_called_once_with(str(session_path))
    assert result is mock_client


def test_get_garmin_client_falls_back_to_full_login_when_session_expired(tmp_path):
    import garmin_coach.garmin_sync as garmin_sync

    session_path = tmp_path / "session.json"
    session_path.write_text("{}")

    mock_client = MagicMock()
    mock_client.login.side_effect = [Exception("expired"), None]
    mock_client.client.dump.return_value = None

    with (
        patch("garmin_coach.garmin_sync.Garmin", return_value=mock_client),
        patch("garmin_coach.garmin_sync.SESSION_PATH", session_path),
    ):
        result = garmin_sync.get_garmin_client("email", "pass")

    assert mock_client.login.call_count == 2
    assert not session_path.exists()


# ── module-level state setters ────────────────────────────────────────────────

def test_set_bot_app_updates_global():
    import garmin_coach.garmin_sync as garmin_sync

    fake_app = MagicMock()
    garmin_sync.set_bot_app(fake_app)
    assert garmin_sync._bot_app is fake_app


def test_set_event_loop_updates_global():
    import garmin_coach.garmin_sync as garmin_sync
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        garmin_sync.set_event_loop(loop)
        assert garmin_sync._bot_loop is loop
    finally:
        loop.close()


def test_provide_mfa_code_sets_code_and_event():
    import garmin_coach.garmin_sync as garmin_sync

    garmin_sync._mfa_event.clear()
    garmin_sync._mfa_code = None

    garmin_sync.provide_mfa_code("123456")

    assert garmin_sync._mfa_code == "123456"
    assert garmin_sync._mfa_event.is_set()
