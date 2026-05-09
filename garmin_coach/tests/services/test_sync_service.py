"""Tests for SyncService."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock


from garmin_coach.services.sync_service import SyncService, SyncSummary


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_repos(empty: bool = True):
    repos = MagicMock()
    repos.activities.is_empty.return_value = empty
    repos.sleep.is_empty.return_value = empty
    repos.hrv.is_empty.return_value = empty
    repos.body_battery.is_empty.return_value = empty
    repos.activities.all.return_value = []
    repos.sleep.all.return_value = []
    repos.hrv.all.return_value = []
    repos.body_battery.all.return_value = []
    repos.activities.upsert_many.return_value = 0
    return repos


def _make_settings(days_history: int = 7):
    settings = MagicMock()
    settings.days_history = days_history
    return settings


def _make_fetcher(
    activities=None,
    sleep_data=None,
    hrv_data=None,
    body_battery_data=None,
):
    fetcher = MagicMock()
    fetcher.fetch_activities.return_value = activities or []
    fetcher.fetch_activity_detail.return_value = None
    fetcher.fetch_sleep.return_value = sleep_data
    fetcher.fetch_hrv.return_value = hrv_data
    fetcher.fetch_body_battery.return_value = body_battery_data
    fetcher.fetch_training_status.return_value = None
    fetcher.fetch_training_readiness.return_value = None
    fetcher.fetch_respiration.return_value = None
    fetcher.fetch_spo2.return_value = None
    fetcher.fetch_stress.return_value = None
    fetcher.fetch_fitness_metrics.return_value = None
    fetcher.fetch_race_predictions.return_value = None
    fetcher.fetch_lactate_threshold.return_value = None
    fetcher.fetch_endurance_score.return_value = None
    return fetcher


def _make_service(repos=None, settings=None, fetcher=None):
    repos = repos or _make_repos()
    settings = settings or _make_settings()
    fetcher = fetcher or _make_fetcher()

    mock_garmin_client = MagicMock()
    mock_garmin_client.authenticate.return_value = MagicMock()
    sync_log = MagicMock()

    service = SyncService(
        garmin_client=mock_garmin_client,
        fetcher_factory=lambda g: fetcher,
        repositories=repos,
        sync_log_repo=sync_log,
        settings=settings,
        purge_days=60,
    )
    return service, sync_log


# ── Happy path ────────────────────────────────────────────────────────────────


def test_run_returns_sync_summary():
    service, _ = _make_service()
    result = service.run()
    assert isinstance(result, SyncSummary)


def test_run_logs_summary():
    service, sync_log = _make_service()
    result = service.run()
    sync_log.log.assert_called_once_with(result.as_dict())


def test_run_summary_as_dict_includes_all_keys():
    service, _ = _make_service()
    d = service.run().as_dict()
    expected_keys = {
        "activities",
        "sleep",
        "hrv",
        "body_battery",
        "training_status",
        "training_readiness",
        "respiration",
        "spo2",
        "stress",
        "fitness_metrics",
        "race_predictions",
        "lactate_threshold",
        "endurance_score",
        "purged",
        "started_at",
        "finished_at",
    }
    assert expected_keys <= set(d)


# ── Activities ────────────────────────────────────────────────────────────────


def test_run_upserts_activities():
    repos = _make_repos()
    repos.activities.upsert_many.return_value = 3
    activity = {
        "activityId": 1,
        "activityName": "Run",
        "startTimeLocal": date.today().isoformat() + " 07:00:00",
    }
    fetcher = _make_fetcher(activities=[activity])
    service, _ = _make_service(repos=repos, fetcher=fetcher)

    result = service.run()

    repos.activities.upsert_many.assert_called_once()
    assert result.activities == 3


def test_run_merges_activity_details():
    repos = _make_repos()
    repos.activities.upsert_many.return_value = 1
    activity = {
        "activityId": 42,
        "startTimeLocal": date.today().isoformat() + " 08:00:00",
    }
    detail = {"normPower": 210}
    fetcher = _make_fetcher(activities=[activity])
    fetcher.fetch_activity_detail.return_value = detail

    service, _ = _make_service(repos=repos, fetcher=fetcher)
    service.run()

    passed_records = repos.activities.upsert_many.call_args[0][0]
    record = list(passed_records)[0]
    assert record["normPower"] == 210


def test_run_activity_fetch_failure_does_not_abort():
    repos = _make_repos()
    fetcher = _make_fetcher()
    fetcher.fetch_activities.side_effect = Exception("network error")

    service, _ = _make_service(repos=repos, fetcher=fetcher)
    result = service.run()  # must not raise

    assert result.activities == 0


# ── Wellness ──────────────────────────────────────────────────────────────────


def test_run_stores_sleep_records():
    repos = _make_repos()
    sleep_raw = {
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
    fetcher = _make_fetcher(sleep_data=sleep_raw)
    service, _ = _make_service(
        repos=repos, settings=_make_settings(days_history=1), fetcher=fetcher
    )
    result = service.run()

    assert result.sleep >= 1
    repos.sleep.upsert.assert_called()


def test_run_stores_hrv_records():
    repos = _make_repos()
    hrv_raw = {
        "hrvSummary": {
            "weeklyAvg": 55,
            "lastNight": 52,
            "lastNight5MinHigh": 70,
            "status": "BALANCED",
            "feedbackPhrase": "HRV_BALANCED_1",
        }
    }
    fetcher = _make_fetcher(hrv_data=hrv_raw)
    service, _ = _make_service(
        repos=repos, settings=_make_settings(days_history=1), fetcher=fetcher
    )
    result = service.run()

    assert result.hrv >= 1
    repos.hrv.upsert.assert_called()


def test_run_stores_body_battery_records():
    repos = _make_repos()
    bb_raw = [{"bodyBatteryValuesArray": [[0, 80], [1, 45], [2, 90]]}]
    fetcher = _make_fetcher(body_battery_data=bb_raw)
    service, _ = _make_service(
        repos=repos, settings=_make_settings(days_history=1), fetcher=fetcher
    )
    result = service.run()

    assert result.body_battery >= 1
    repos.body_battery.upsert.assert_called()


# ── Purge ─────────────────────────────────────────────────────────────────────


def test_run_purges_wellness_but_not_activities():
    repos = _make_repos()
    service, _ = _make_service(repos=repos)
    service.run()

    repos.sleep.delete_older_than.assert_called()
    repos.hrv.delete_older_than.assert_called()
    repos.body_battery.delete_older_than.assert_called()
    # activities must NOT be purged
    repos.activities.delete_older_than.assert_not_called()


def test_run_purge_counts_in_summary():
    repos = _make_repos()
    repos.sleep.delete_older_than.return_value = 5
    repos.hrv.delete_older_than.return_value = 3
    repos.body_battery.delete_older_than.return_value = 2
    repos.training_status.delete_older_than.return_value = 0
    repos.training_readiness.delete_older_than.return_value = 0
    repos.respiration.delete_older_than.return_value = 0
    repos.spo2.delete_older_than.return_value = 0
    repos.stress.delete_older_than.return_value = 0

    service, _ = _make_service(repos=repos)
    result = service.run()

    assert result.purged["sleep"] == 5
    assert result.purged["hrv"] == 3
    assert result.purged["body_battery"] == 2
    assert result.purged["activities"] == 0


# ── Fitness snapshots ─────────────────────────────────────────────────────────


def test_run_stores_fitness_metrics_when_available():
    repos = _make_repos()
    fm_raw = [{"vO2MaxValue": 52.0}]
    fetcher = _make_fetcher()
    fetcher.fetch_fitness_metrics.return_value = fm_raw

    service, _ = _make_service(repos=repos, fetcher=fetcher)
    result = service.run()

    repos.fitness_metrics.replace.assert_called_once()
    assert result.fitness_metrics == 1


def test_run_skips_fitness_metrics_when_none():
    repos = _make_repos()
    fetcher = _make_fetcher()
    fetcher.fetch_fitness_metrics.return_value = None

    service, _ = _make_service(repos=repos, fetcher=fetcher)
    result = service.run()

    repos.fitness_metrics.replace.assert_not_called()
    assert result.fitness_metrics == 0


# ── Window computation ────────────────────────────────────────────────────────


def test_run_uses_default_days_when_db_empty():
    repos = _make_repos(empty=True)
    fetcher = _make_fetcher()
    settings = _make_settings(days_history=14)

    service, _ = _make_service(repos=repos, settings=settings, fetcher=fetcher)
    service.run()

    call_args = fetcher.fetch_activities.call_args
    start_used = call_args[0][0]
    expected_start = (date.today() - timedelta(days=14)).isoformat()
    assert start_used == expected_start


def test_run_uses_last_db_date_when_not_empty():
    last_date = (date.today() - timedelta(days=3)).isoformat()
    repos = _make_repos(empty=False)
    repos.activities.all.return_value = [{"startTimeLocal": last_date + " 06:00:00"}]
    repos.sleep.all.return_value = []
    repos.hrv.all.return_value = []
    repos.body_battery.all.return_value = []

    fetcher = _make_fetcher()
    service, _ = _make_service(repos=repos, fetcher=fetcher)
    service.run()

    call_args = fetcher.fetch_activities.call_args
    start_used = call_args[0][0]
    assert start_used == last_date
