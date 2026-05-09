"""
services/sync_service.py
Orchestrates a full Garmin data sync: auth → fetch → upsert → purge → log.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable

from garminconnect import Garmin

from garmin_coach.infrastructure.garmin.data_fetcher import GarminDataFetcher
from garmin_coach.services.sync_helpers import (
    compute_sync_window,
    daterange,
    merge_activity_details,
)

if TYPE_CHECKING:
    from garmin_coach.app.config import Settings
    from garmin_coach.app.container import Repositories
    from garmin_coach.infrastructure.db.sync_log_repository import SyncLogRepository
    from garmin_coach.infrastructure.garmin.client import GarminClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SyncSummary:
    activities: int
    sleep: int
    hrv: int
    body_battery: int
    training_status: int
    training_readiness: int
    respiration: int
    spo2: int
    stress: int
    fitness_metrics: int
    race_predictions: int
    lactate_threshold: int
    endurance_score: int
    purged: dict
    started_at: str
    finished_at: str

    def as_dict(self) -> dict:
        return {
            "activities": self.activities,
            "sleep": self.sleep,
            "hrv": self.hrv,
            "body_battery": self.body_battery,
            "training_status": self.training_status,
            "training_readiness": self.training_readiness,
            "respiration": self.respiration,
            "spo2": self.spo2,
            "stress": self.stress,
            "fitness_metrics": self.fitness_metrics,
            "race_predictions": self.race_predictions,
            "lactate_threshold": self.lactate_threshold,
            "endurance_score": self.endurance_score,
            "purged": self.purged,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class SyncService:
    def __init__(
        self,
        garmin_client: "GarminClient",
        fetcher_factory: Callable[[Garmin], GarminDataFetcher],
        repositories: "Repositories",
        sync_log_repo: "SyncLogRepository",
        settings: "Settings",
        purge_days: int = 60,
    ) -> None:
        self._client = garmin_client
        self._fetcher_factory = fetcher_factory
        self._repos = repositories
        self._sync_log = sync_log_repo
        self._settings = settings
        self._purge_days = purge_days

    def run(self) -> SyncSummary:
        started_at = datetime.now(timezone.utc).isoformat()
        garmin = self._client.authenticate()
        fetcher = self._fetcher_factory(garmin)

        start_iso, end_iso = compute_sync_window(
            self._repos, self._settings.days_history
        )

        purged = self._purge_wellness(self._purge_days)
        logger.info("Purged records older than %dd: %s", self._purge_days, purged)

        counts: dict[str, int] = {
            "activities": 0,
            "sleep": 0,
            "hrv": 0,
            "body_battery": 0,
            "training_status": 0,
            "training_readiness": 0,
            "respiration": 0,
            "spo2": 0,
            "stress": 0,
            "fitness_metrics": 0,
            "race_predictions": 0,
            "lactate_threshold": 0,
            "endurance_score": 0,
        }

        # ── Activities ────────────────────────────────────────────────────────
        try:
            raw_activities = fetcher.fetch_activities(start_iso, end_iso)
            activities = merge_activity_details(
                raw_activities, fetcher.fetch_activity_detail
            )
            from datetime import datetime as _dt, timezone as _tz

            synced_at = _dt.now(_tz.utc).isoformat()
            enriched = [
                {
                    **a,
                    "activityId": str(a.get("activityId", "")),
                    "synced_at": synced_at,
                }
                for a in activities
            ]
            counts["activities"] = self._repos.activities.upsert_many(enriched)
            logger.info("Activities: %d records", counts["activities"])
        except Exception as exc:
            logger.error("Error fetching activities: %s", exc)

        # ── Daily wellness ────────────────────────────────────────────────────
        wellness_specs = [
            ("sleep", fetcher.fetch_sleep, self._repos.sleep, self._extract_sleep),
            ("hrv", fetcher.fetch_hrv, self._repos.hrv, self._extract_hrv),
            (
                "body_battery",
                fetcher.fetch_body_battery,
                self._repos.body_battery,
                self._extract_body_battery,
            ),
            (
                "training_status",
                fetcher.fetch_training_status,
                self._repos.training_status,
                lambda r, d: r.get("trainingStatusDTO") or (r if r else None),
            ),
            (
                "training_readiness",
                fetcher.fetch_training_readiness,
                self._repos.training_readiness,
                lambda r, d: r.get("trainingReadinessDTO")
                if isinstance(r, dict)
                else (r[0] if isinstance(r, list) and r else None),
            ),
            (
                "respiration",
                fetcher.fetch_respiration,
                self._repos.respiration,
                self._extract_respiration,
            ),
            ("spo2", fetcher.fetch_spo2, self._repos.spo2, self._extract_spo2),
            ("stress", fetcher.fetch_stress, self._repos.stress, self._extract_stress),
        ]

        from datetime import datetime as _dt2, timezone as _tz2

        for table_name, fetch_fn, repo, extractor in wellness_specs:
            n = 0
            for day_str in daterange(start_iso, end_iso):
                try:
                    raw = fetch_fn(day_str)
                    if raw is None:
                        continue
                    data = extractor(raw, day_str)
                    if not data:
                        continue
                    record = {
                        "date": day_str,
                        **data,
                        "synced_at": _dt2.now(_tz2.utc).isoformat(),
                    }
                    repo.upsert(record)
                    n += 1
                except Exception:
                    pass
            counts[table_name] = n
            logger.info("%s: %d records", table_name, n)

        # ── Fitness snapshots ─────────────────────────────────────────────────
        from datetime import datetime as _dt3, timezone as _tz3, date as _date

        today_str = _date.today().isoformat()

        try:
            raw_fm = fetcher.fetch_fitness_metrics()
            if raw_fm is not None:
                vo2max = self._parse_vo2max(raw_fm)
                self._repos.fitness_metrics.replace(
                    {
                        "date": today_str,
                        "vo2max": vo2max,
                        "maxMetrics": raw_fm,
                        "synced_at": _dt3.now(_tz3.utc).isoformat(),
                    }
                )
                counts["fitness_metrics"] = 1
                logger.info("VO2max: %s", vo2max)
        except Exception as exc:
            logger.debug("No fitness metrics: %s", exc)

        try:
            raw_rp = fetcher.fetch_race_predictions()
            if raw_rp is not None:
                self._repos.race_predictions.replace(
                    {
                        "date": today_str,
                        "predictions": raw_rp,
                        "synced_at": _dt3.now(_tz3.utc).isoformat(),
                    }
                )
                counts["race_predictions"] = 1
                logger.info("Race predictions updated")
        except Exception as exc:
            logger.debug("No race predictions: %s", exc)

        try:
            raw_lt = fetcher.fetch_lactate_threshold()
            if raw_lt is not None:
                self._repos.lactate_threshold.replace(
                    {
                        "date": today_str,
                        **raw_lt,
                        "synced_at": _dt3.now(_tz3.utc).isoformat(),
                    }
                )
                counts["lactate_threshold"] = 1
                logger.info("Lactate threshold updated")
        except Exception as exc:
            logger.debug("No lactate threshold: %s", exc)

        try:
            raw_es = fetcher.fetch_endurance_score()
            if raw_es is not None:
                self._repos.endurance_score.replace(
                    {
                        "date": today_str,
                        "data": raw_es,
                        "synced_at": _dt3.now(_tz3.utc).isoformat(),
                    }
                )
                counts["endurance_score"] = 1
                logger.info("Endurance score updated")
        except Exception as exc:
            logger.debug("No endurance score: %s", exc)

        finished_at = datetime.now(timezone.utc).isoformat()
        summary = SyncSummary(
            **counts,
            purged=purged,
            started_at=started_at,
            finished_at=finished_at,
        )
        self._sync_log.log(summary.as_dict())
        logger.info("Sync completed: %s", counts)
        return summary

    # ── Private extraction helpers ────────────────────────────────────────────

    @staticmethod
    def _extract_sleep(raw: dict, day_str: str) -> dict | None:
        daily = raw.get("dailySleepDTO", {})
        if not daily:
            return None
        return {
            "duration_s": daily.get("sleepTimeSeconds"),
            "deep_s": daily.get("deepSleepSeconds"),
            "light_s": daily.get("lightSleepSeconds"),
            "rem_s": daily.get("remSleepSeconds"),
            "awake_s": daily.get("awakeSleepSeconds"),
            "score": daily.get("sleepScores", {}).get("overall", {}).get("value"),
            "restingHR": daily.get("restingHeartRate"),
        }

    @staticmethod
    def _extract_hrv(raw: dict, day_str: str) -> dict | None:
        summary = raw.get("hrvSummary", {})
        if not summary:
            return None
        return {
            "weeklyAvg": summary.get("weeklyAvg"),
            "lastNight": summary.get("lastNight"),
            "lastNight5MinHigh": summary.get("lastNight5MinHigh"),
            "status": summary.get("status"),
            "feedbackPhrase": summary.get("feedbackPhrase"),
        }

    @staticmethod
    def _extract_body_battery(raw: list, day_str: str) -> dict | None:
        if not raw:
            return None
        values = (
            raw[0].get("bodyBatteryValuesArray", []) if isinstance(raw, list) else []
        )
        charged = max((v[1] for v in values if v), default=None)
        drained = min((v[1] for v in values if v), default=None)
        if charged is None and drained is None:
            return None
        return {"max": charged, "min": drained}

    @staticmethod
    def _extract_respiration(raw: dict, day_str: str) -> dict | None:
        keys = (
            "avgWakingRespirationValue",
            "avgSleepRespirationValue",
            "highestRespirationValue",
            "lowestRespirationValue",
        )
        data = {k: raw[k] for k in keys if raw.get(k) is not None}
        return data or None

    @staticmethod
    def _extract_spo2(raw: dict, day_str: str) -> dict | None:
        keys = ("averageSpO2", "lowestSpO2", "lastSevenDaysAvgSpO2")
        data = {k: raw[k] for k in keys if raw.get(k) is not None}
        return data or None

    @staticmethod
    def _extract_stress(raw: dict, day_str: str) -> dict | None:
        keys = ("avgStressLevel", "maxStressLevel")
        data = {k: raw[k] for k in keys if raw.get(k) is not None}
        return data or None

    @staticmethod
    def _parse_vo2max(raw) -> float | None:
        try:
            if isinstance(raw, list):
                for item in raw:
                    v = item.get("vO2MaxValue") if isinstance(item, dict) else None
                    if v is not None:
                        return v
            else:
                metrics_map = raw.get("allMetrics", {}).get("metricsMap", {})
                vo2max_list = metrics_map.get("VO2MAX_VALUE", [])
                if vo2max_list:
                    return vo2max_list[-1].get("value")
        except Exception:
            pass
        return None

    def _purge_wellness(self, days: int) -> dict:
        from datetime import date as _date, timedelta as _td

        cutoff = (_date.today() - _td(days=days)).isoformat()
        removed: dict[str, int] = {"activities": 0}
        wellness_repos = [
            ("sleep", self._repos.sleep),
            ("hrv", self._repos.hrv),
            ("body_battery", self._repos.body_battery),
            ("training_status", self._repos.training_status),
            ("training_readiness", self._repos.training_readiness),
            ("respiration", self._repos.respiration),
            ("spo2", self._repos.spo2),
            ("stress", self._repos.stress),
        ]
        for name, repo in wellness_repos:
            removed[name] = repo.delete_older_than("date", cutoff)
        return removed
