"""
services/context_builder.py
ContextBuilder: wraps projection functions and repository access to produce
compact LLM context dicts from TinyDB data.
"""

from __future__ import annotations

from datetime import date, timedelta

from garmin_coach.services.projections import (
    aggregate_series,
    slim_activity,
    slim_body_battery,
    slim_endurance_score,
    slim_fitness_metrics,
    slim_hrv,
    slim_race_predictions,
    slim_lactate_threshold,
    slim_respiration,
    slim_sleep,
    slim_spo2,
    slim_stress,
    slim_training_readiness,
    slim_training_status,
)

NOTABLE_RUNS_LIMIT = 3


class ContextBuilder:
    """Builds compact LLM context from repository data.

    Injected with all repositories needed to fetch data. Call `.build(days)`
    to get a compact dict suitable for passing to the LLM.
    """

    def __init__(
        self,
        activity_repo,
        sleep_repo,
        hrv_repo,
        body_battery_repo,
        training_status_repo,
        training_readiness_repo,
        respiration_repo,
        spo2_repo,
        stress_repo,
        fitness_metrics_repo,
        race_predictions_repo,
        lactate_repo,
        endurance_repo,
        memory_repo,
    ) -> None:
        self._activity_repo = activity_repo
        self._sleep_repo = sleep_repo
        self._hrv_repo = hrv_repo
        self._body_battery_repo = body_battery_repo
        self._training_status_repo = training_status_repo
        self._training_readiness_repo = training_readiness_repo
        self._respiration_repo = respiration_repo
        self._spo2_repo = spo2_repo
        self._stress_repo = stress_repo
        self._fitness_metrics_repo = fitness_metrics_repo
        self._race_predictions_repo = race_predictions_repo
        self._lactate_repo = lactate_repo
        self._endurance_repo = endurance_repo
        self._memory_repo = memory_repo

    def build_raw(self, days: int = 14) -> dict:
        """Return raw (un-slimmed) data from all repos for the given window."""
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        today = date.today().isoformat()

        def _date_sorted(rows: list[dict]) -> list[dict]:
            return sorted(rows, key=lambda r: r.get("date", ""), reverse=True)

        activities = sorted(
            [
                a
                for a in self._activity_repo.all()
                if bool(a.get("startTimeLocal"))
                and a.get("startTimeLocal", "") >= cutoff
            ],
            key=lambda x: x.get("startTimeLocal", ""),
            reverse=True,
        )[:20]

        return {
            "activities": activities,
            "sleep": _date_sorted(
                self._sleep_repo.find_by_date_range("date", cutoff, today)
            ),
            "hrv": _date_sorted(
                self._hrv_repo.find_by_date_range("date", cutoff, today)
            ),
            "body_battery": _date_sorted(
                self._body_battery_repo.find_by_date_range("date", cutoff, today)
            ),
            "training_status": _date_sorted(
                self._training_status_repo.find_by_date_range("date", cutoff, today)
            ),
            "training_readiness": _date_sorted(
                self._training_readiness_repo.find_by_date_range("date", cutoff, today)
            ),
            "respiration": _date_sorted(
                self._respiration_repo.find_by_date_range("date", cutoff, today)
            ),
            "spo2": _date_sorted(
                self._spo2_repo.find_by_date_range("date", cutoff, today)
            ),
            "stress": _date_sorted(
                self._stress_repo.find_by_date_range("date", cutoff, today)
            ),
            "fitness_metrics": self._fitness_metrics_repo.latest(),
            "race_predictions": self._race_predictions_repo.latest(),
            "lactate_threshold": self._lactate_repo.latest(),
            "endurance_score": self._endurance_repo.latest(),
            "memory": self._memory_repo.all(),
            "days_covered": days,
        }

    def build(self, days: int = 7, max_activities: int = 15) -> dict:
        """Return a compact context dict slimmed for LLM consumption."""
        raw = self.build_raw(days=days)
        return _compact(raw, max_activities=max_activities)


def _compact(raw: dict, *, max_activities: int = 15) -> dict:
    """Project raw repo data into a compact dict for the LLM."""
    slim_acts = [slim_activity(a) for a in raw.get("activities", [])]
    activities = slim_acts[:max_activities]
    notable_runs = sorted(
        (
            a
            for a in slim_acts
            if a.get("is_run") and isinstance(a.get("distance_km"), (int, float))
        ),
        key=lambda a: a["distance_km"],
        reverse=True,
    )[:NOTABLE_RUNS_LIMIT]

    sleep_records = [slim_sleep(s) for s in raw.get("sleep", [])]
    hrv_records = [slim_hrv(h) for h in raw.get("hrv", [])]
    bb_records = [slim_body_battery(b) for b in raw.get("body_battery", [])]
    resp_records = [slim_respiration(r) for r in raw.get("respiration", [])]
    spo2_records = [slim_spo2(s) for s in raw.get("spo2", [])]
    stress_records = [slim_stress(s) for s in raw.get("stress", [])]
    ts_records = [slim_training_status(t) for t in raw.get("training_status", [])]
    tr_records = [slim_training_readiness(t) for t in raw.get("training_readiness", [])]

    return {
        "days_covered": raw.get("days_covered"),
        "activities": activities,
        "notable_runs": notable_runs,
        "sleep": {
            "recent": sleep_records[:7],
            "score_summary": aggregate_series(sleep_records, "score"),
            "total_h_summary": aggregate_series(sleep_records, "total_h"),
            "restingHR_summary": aggregate_series(sleep_records, "restingHR"),
        },
        "hrv": {
            "recent": hrv_records[:7],
            "lastNight_summary": aggregate_series(hrv_records, "lastNight"),
            "weeklyAvg_summary": aggregate_series(hrv_records, "weeklyAvg"),
        },
        "body_battery": {
            "recent": bb_records[:7],
            "max_summary": aggregate_series(bb_records, "max"),
            "min_summary": aggregate_series(bb_records, "min"),
        },
        "respiration": {"recent": resp_records[:7]},
        "spo2": {"recent": spo2_records[:7]},
        "stress": {
            "recent": stress_records[:7],
            "avg_summary": aggregate_series(stress_records, "avgStressLevel"),
        },
        "training_status": {"recent": ts_records[:5]},
        "training_readiness": {
            "recent": tr_records[:5],
            "score_summary": aggregate_series(tr_records, "score"),
        },
        "fitness_metrics": slim_fitness_metrics(raw.get("fitness_metrics")),
        "race_predictions": slim_race_predictions(raw.get("race_predictions")),
        "lactate_threshold": slim_lactate_threshold(raw.get("lactate_threshold")),
        "endurance_score": slim_endurance_score(raw.get("endurance_score")),
        "memory": raw.get("memory", []),
    }
