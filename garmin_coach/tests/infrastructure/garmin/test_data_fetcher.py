"""Tests for GarminDataFetcher."""

from __future__ import annotations

from unittest.mock import MagicMock


from garmin_coach.infrastructure.garmin.data_fetcher import GarminDataFetcher


def _make_garmin(**overrides) -> MagicMock:
    g = MagicMock()
    for attr, val in overrides.items():
        setattr(g, attr, val)
    return g


# ── fetch_activities ──────────────────────────────────────────────────────────


def test_fetch_activities_happy():
    g = _make_garmin()
    g.get_activities_by_date.return_value = [{"activityId": 1}]
    fetcher = GarminDataFetcher(g)
    result = fetcher.fetch_activities("2024-01-01", "2024-01-07")
    assert result == [{"activityId": 1}]
    g.get_activities_by_date.assert_called_once_with("2024-01-01", "2024-01-07", 200)


def test_fetch_activities_exception_returns_empty():
    g = _make_garmin()
    g.get_activities_by_date.side_effect = Exception("API down")
    fetcher = GarminDataFetcher(g)
    result = fetcher.fetch_activities("2024-01-01", "2024-01-07")
    assert result == []


# ── fetch_activity_detail ─────────────────────────────────────────────────────


def test_fetch_activity_detail_happy():
    g = _make_garmin()
    g.get_activity.return_value = {"activityId": "42", "normPower": 200}
    fetcher = GarminDataFetcher(g)
    result = fetcher.fetch_activity_detail("42")
    assert result == {"activityId": "42", "normPower": 200}


def test_fetch_activity_detail_exception_returns_none():
    g = _make_garmin()
    g.get_activity.side_effect = Exception("not found")
    fetcher = GarminDataFetcher(g)
    assert fetcher.fetch_activity_detail("99") is None


# ── fetch_sleep ───────────────────────────────────────────────────────────────


def test_fetch_sleep_happy():
    payload = {"dailySleepDTO": {"sleepTimeSeconds": 28800}}
    g = _make_garmin()
    g.get_sleep_data.return_value = payload
    fetcher = GarminDataFetcher(g)
    assert fetcher.fetch_sleep("2024-01-01") == payload


def test_fetch_sleep_exception_returns_none():
    g = _make_garmin()
    g.get_sleep_data.side_effect = Exception("timeout")
    fetcher = GarminDataFetcher(g)
    assert fetcher.fetch_sleep("2024-01-01") is None


# ── fetch_hrv ─────────────────────────────────────────────────────────────────


def test_fetch_hrv_happy():
    payload = {"hrvSummary": {"weeklyAvg": 55}}
    g = _make_garmin()
    g.get_hrv_data.return_value = payload
    fetcher = GarminDataFetcher(g)
    assert fetcher.fetch_hrv("2024-01-01") == payload


def test_fetch_hrv_exception_returns_none():
    g = _make_garmin()
    g.get_hrv_data.side_effect = Exception("error")
    fetcher = GarminDataFetcher(g)
    assert fetcher.fetch_hrv("2024-01-01") is None


# ── fetch_body_battery ────────────────────────────────────────────────────────


def test_fetch_body_battery_happy():
    payload = [{"bodyBatteryValuesArray": [[0, 80]]}]
    g = _make_garmin()
    g.get_body_battery.return_value = payload
    fetcher = GarminDataFetcher(g)
    assert fetcher.fetch_body_battery("2024-01-01") == payload


def test_fetch_body_battery_exception_returns_none():
    g = _make_garmin()
    g.get_body_battery.side_effect = Exception("error")
    fetcher = GarminDataFetcher(g)
    assert fetcher.fetch_body_battery("2024-01-01") is None


# ── fetch_training_status ─────────────────────────────────────────────────────


def test_fetch_training_status_happy():
    payload = {"trainingStatusDTO": {"trainingStatus": "PRODUCTIVE"}}
    g = _make_garmin()
    g.get_training_status.return_value = payload
    fetcher = GarminDataFetcher(g)
    assert fetcher.fetch_training_status("2024-01-01") == payload


def test_fetch_training_status_exception_returns_none():
    g = _make_garmin()
    g.get_training_status.side_effect = Exception("error")
    fetcher = GarminDataFetcher(g)
    assert fetcher.fetch_training_status("2024-01-01") is None


# ── fetch_training_readiness ──────────────────────────────────────────────────


def test_fetch_training_readiness_happy():
    payload = {"trainingReadinessDTO": {"score": 72}}
    g = _make_garmin()
    g.get_training_readiness.return_value = payload
    fetcher = GarminDataFetcher(g)
    assert fetcher.fetch_training_readiness("2024-01-01") == payload


def test_fetch_training_readiness_exception_returns_none():
    g = _make_garmin()
    g.get_training_readiness.side_effect = Exception("error")
    fetcher = GarminDataFetcher(g)
    assert fetcher.fetch_training_readiness("2024-01-01") is None


# ── fetch_respiration ─────────────────────────────────────────────────────────


def test_fetch_respiration_happy():
    payload = {"avgWakingRespirationValue": 15.2}
    g = _make_garmin()
    g.get_respiration_data.return_value = payload
    fetcher = GarminDataFetcher(g)
    assert fetcher.fetch_respiration("2024-01-01") == payload


def test_fetch_respiration_exception_returns_none():
    g = _make_garmin()
    g.get_respiration_data.side_effect = Exception("error")
    fetcher = GarminDataFetcher(g)
    assert fetcher.fetch_respiration("2024-01-01") is None


# ── fetch_spo2 ────────────────────────────────────────────────────────────────


def test_fetch_spo2_happy():
    payload = {"averageSpO2": 97}
    g = _make_garmin()
    g.get_spo2_data.return_value = payload
    fetcher = GarminDataFetcher(g)
    assert fetcher.fetch_spo2("2024-01-01") == payload


def test_fetch_spo2_exception_returns_none():
    g = _make_garmin()
    g.get_spo2_data.side_effect = Exception("error")
    fetcher = GarminDataFetcher(g)
    assert fetcher.fetch_spo2("2024-01-01") is None


# ── fetch_stress ──────────────────────────────────────────────────────────────


def test_fetch_stress_happy():
    payload = {"avgStressLevel": 32}
    g = _make_garmin()
    g.get_stress_data.return_value = payload
    fetcher = GarminDataFetcher(g)
    assert fetcher.fetch_stress("2024-01-01") == payload


def test_fetch_stress_exception_returns_none():
    g = _make_garmin()
    g.get_stress_data.side_effect = Exception("error")
    fetcher = GarminDataFetcher(g)
    assert fetcher.fetch_stress("2024-01-01") is None


# ── fetch_fitness_metrics ─────────────────────────────────────────────────────


def test_fetch_fitness_metrics_happy():
    payload = {"allMetrics": {"metricsMap": {"VO2MAX_VALUE": [{"value": 52.0}]}}}
    g = _make_garmin()
    g.get_max_metrics.return_value = payload
    fetcher = GarminDataFetcher(g)
    assert fetcher.fetch_fitness_metrics() == payload


def test_fetch_fitness_metrics_exception_returns_none():
    g = _make_garmin()
    g.get_max_metrics.side_effect = Exception("error")
    fetcher = GarminDataFetcher(g)
    assert fetcher.fetch_fitness_metrics() is None


# ── fetch_race_predictions ────────────────────────────────────────────────────


def test_fetch_race_predictions_happy():
    payload = {"predictions": []}
    g = _make_garmin()
    g.get_race_predictions.return_value = payload
    fetcher = GarminDataFetcher(g)
    assert fetcher.fetch_race_predictions() == payload


def test_fetch_race_predictions_exception_returns_none():
    g = _make_garmin()
    g.get_race_predictions.side_effect = Exception("error")
    fetcher = GarminDataFetcher(g)
    assert fetcher.fetch_race_predictions() is None


# ── fetch_lactate_threshold ───────────────────────────────────────────────────


def test_fetch_lactate_threshold_happy():
    payload = {"lactateThresholdHeartRate": 162}
    g = _make_garmin()
    g.get_lactate_threshold.return_value = payload
    fetcher = GarminDataFetcher(g)
    assert fetcher.fetch_lactate_threshold() == payload


def test_fetch_lactate_threshold_exception_returns_none():
    g = _make_garmin()
    g.get_lactate_threshold.side_effect = Exception("error")
    fetcher = GarminDataFetcher(g)
    assert fetcher.fetch_lactate_threshold() is None


# ── fetch_endurance_score ─────────────────────────────────────────────────────


def test_fetch_endurance_score_happy():
    payload = {"enduranceScore": 85}
    g = _make_garmin()
    g.get_endurance_score.return_value = payload
    fetcher = GarminDataFetcher(g)
    assert fetcher.fetch_endurance_score() == payload


def test_fetch_endurance_score_exception_returns_none():
    g = _make_garmin()
    g.get_endurance_score.side_effect = Exception("error")
    fetcher = GarminDataFetcher(g)
    assert fetcher.fetch_endurance_score() is None
