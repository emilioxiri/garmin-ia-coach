"""
infrastructure/garmin/data_fetcher.py
Pure data fetching from the Garmin Connect API.
No writes — each method returns raw API dicts or None/[] on failure.
"""

from __future__ import annotations

import logging
from typing import Any

from garminconnect import Garmin

logger = logging.getLogger(__name__)


def _safe(name: str, fn, *args, **kwargs) -> Any:
    """Call fn(*args, **kwargs) and return None on any exception."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        logger.debug("Garmin fetch '%s' failed: %s", name, exc)
        return None


class GarminDataFetcher:
    """One public method per Garmin Connect endpoint. No upserts."""

    def __init__(self, garmin: Garmin) -> None:
        self._g = garmin

    def fetch_activities(
        self, start_date: str, end_date: str, limit: int = 200
    ) -> list[dict]:
        result = _safe(
            "activities",
            self._g.get_activities_by_date,
            start_date,
            end_date,
            limit,
        )
        return result if isinstance(result, list) else []

    def fetch_activity_detail(self, activity_id: str) -> dict | None:
        return _safe("activity_detail", self._g.get_activity, activity_id)

    def fetch_sleep(self, date_iso: str) -> dict | None:
        return _safe("sleep", self._g.get_sleep_data, date_iso)

    def fetch_hrv(self, date_iso: str) -> dict | None:
        return _safe("hrv", self._g.get_hrv_data, date_iso)

    def fetch_body_battery(self, date_iso: str) -> list[dict] | None:
        result = _safe("body_battery", self._g.get_body_battery, date_iso, date_iso)
        if isinstance(result, list):
            return result
        return None

    def fetch_training_status(self, date_iso: str) -> dict | None:
        return _safe("training_status", self._g.get_training_status, date_iso)

    def fetch_training_readiness(self, date_iso: str) -> list[dict] | dict | None:
        return _safe("training_readiness", self._g.get_training_readiness, date_iso)

    def fetch_respiration(self, date_iso: str) -> dict | None:
        return _safe("respiration", self._g.get_respiration_data, date_iso)

    def fetch_spo2(self, date_iso: str) -> dict | None:
        return _safe("spo2", self._g.get_spo2_data, date_iso)

    def fetch_stress(self, date_iso: str) -> dict | None:
        return _safe("stress", self._g.get_stress_data, date_iso)

    def fetch_fitness_metrics(self) -> dict | None:
        from datetime import date

        return _safe(
            "fitness_metrics", self._g.get_max_metrics, date.today().isoformat()
        )

    def fetch_race_predictions(self) -> dict | None:
        from datetime import date, timedelta

        today = date.today()
        start = (today - timedelta(days=30)).isoformat()
        return _safe(
            "race_predictions", self._g.get_race_predictions, start, today.isoformat()
        )

    def fetch_lactate_threshold(self) -> dict | None:
        return _safe("lactate_threshold", self._g.get_lactate_threshold)

    def fetch_endurance_score(self) -> dict | None:
        from datetime import date, timedelta

        today = date.today()
        start = (today - timedelta(days=30)).isoformat()
        return _safe(
            "endurance_score", self._g.get_endurance_score, start, today.isoformat()
        )
