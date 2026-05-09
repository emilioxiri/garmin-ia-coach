"""
infrastructure/db/activity_repository.py
Repository for Garmin activities with query helpers and PR computation.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from tinydb import TinyDB

from garmin_coach.domain.activity import RUN_TYPES
from garmin_coach.domain.fitness import PersonalRecord
from garmin_coach.infrastructure.db.base_repository import BaseRepository

# Canonical race distances with asymmetric tolerances.
_PR_DISTANCES = (
    {"label": "1K", "meters": 1_000, "tolerance": 0.05},
    {"label": "5K", "meters": 5_000, "tolerance": 0.03},
    {"label": "10K", "meters": 10_000, "tolerance": 0.03},
    {"label": "half_marathon", "meters": 21_097, "tolerance": 0.02},
    {"label": "marathon", "meters": 42_195, "tolerance": 0.02},
)

_WEEKDAYS_ES_INDEX = {
    "lunes": 0,
    "martes": 1,
    "miércoles": 2,
    "miercoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sábado": 5,
    "sabado": 5,
    "domingo": 6,
}


def _type_key(act: dict) -> str | None:
    t = act.get("activityType")
    if isinstance(t, dict):
        return t.get("typeKey")
    if isinstance(t, str):
        return t
    return None


def _format_duration(seconds: Any) -> str | None:
    if not isinstance(seconds, (int, float)) or seconds < 0:
        return None
    total = int(round(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:d}:{s:02d}"


class ActivityRepository(BaseRepository):
    def __init__(self, db: TinyDB) -> None:
        super().__init__(db, "activities", primary_key="activityId")

    def latest_date(self) -> str | None:
        """Return max startTimeLocal[:10] across all activities, or None."""
        dates = []
        for act in self.all():
            start = act.get("startTimeLocal") or act.get("startTime", "")
            if start and len(start) >= 10:
                dates.append(start[:10])
        return max(dates) if dates else None

    def find_runs_in_window(self, start_iso: str, end_iso: str) -> list[dict]:
        """Return running activities whose startTimeLocal falls in [start_iso, end_iso]."""
        results = []
        for act in self.all():
            start = act.get("startTimeLocal", "")
            if not isinstance(start, str) or len(start) < 10:
                continue
            act_date = start[:10]
            if start_iso <= act_date <= end_iso and _type_key(act) in RUN_TYPES:
                results.append(act)
        results.sort(key=lambda a: a.get("startTimeLocal", ""), reverse=True)
        return results

    def find_by_weekday(self, weekday_es: str, days_back: int = 30) -> list[dict]:
        """Return activities matching the given Spanish weekday name."""
        idx = _WEEKDAYS_ES_INDEX.get(weekday_es.strip().lower())
        if idx is None:
            return []
        cutoff = (date.today() - timedelta(days=days_back)).isoformat()
        results = []
        for act in self.all():
            start = act.get("startTimeLocal", "")
            if not isinstance(start, str) or len(start) < 10:
                continue
            if start[:10] < cutoff:
                continue
            try:
                d = date.fromisoformat(start[:10])
            except ValueError:
                continue
            if d.weekday() == idx:
                results.append(act)
        results.sort(key=lambda a: a.get("startTimeLocal", ""), reverse=True)
        return results

    def find_by_min_distance_km(self, min_km: float, days_back: int = 30) -> list[dict]:
        """Return activities with distance >= min_km within the last days_back days."""
        cutoff = (date.today() - timedelta(days=days_back)).isoformat()
        results = []
        for act in self.all():
            start = act.get("startTimeLocal", "")
            if not isinstance(start, str) or len(start) < 10:
                continue
            if start[:10] < cutoff:
                continue
            dist = act.get("distance")
            if isinstance(dist, (int, float)) and dist / 1000 >= min_km:
                results.append(act)
        results.sort(key=lambda a: a.get("startTimeLocal", ""), reverse=True)
        return results

    def find_by_type(self, activity_type: str, days_back: int = 30) -> list[dict]:
        """Return activities matching the given Garmin typeKey."""
        cutoff = (date.today() - timedelta(days=days_back)).isoformat()
        results = []
        for act in self.all():
            start = act.get("startTimeLocal", "")
            if not isinstance(start, str) or len(start) < 10:
                continue
            if start[:10] < cutoff:
                continue
            if _type_key(act) == activity_type:
                results.append(act)
        results.sort(key=lambda a: a.get("startTimeLocal", ""), reverse=True)
        return results

    def compute_personal_records(self) -> dict[str, PersonalRecord | None]:
        """Compute PRs over all running activities.

        Returns a dict keyed by distance label ('1K', '5K', '10K',
        'half_marathon', 'marathon', 'longest_run').
        """
        activities = self.all()
        bests: dict[str, PersonalRecord | None] = {}
        for spec in _PR_DISTANCES:
            bests[spec["label"]] = self._pr_for_distance(
                activities, spec["meters"], spec["tolerance"], spec["label"]
            )
        bests["longest_run"] = self._longest_run_record(activities)
        return bests

    def _pr_for_distance(
        self,
        activities: list[dict],
        target_m: int,
        tolerance: float,
        label: str,
    ) -> PersonalRecord | None:
        lo = target_m * (1 - tolerance)
        hi = target_m * (1 + tolerance)
        candidates: list[tuple[float, dict]] = []
        for act in activities:
            if _type_key(act) not in RUN_TYPES:
                continue
            distance = act.get("distance")
            duration = act.get("duration")
            if not isinstance(distance, (int, float)) or not isinstance(
                duration, (int, float)
            ):
                continue
            if duration <= 0 or not (lo <= distance <= hi):
                continue
            candidates.append((duration, act))
        if not candidates:
            return None
        duration, act = min(candidates, key=lambda x: x[0])
        distance = act["distance"]
        pace_str: str | None = None
        if distance and distance > 0:
            pace_sec = (1000 / distance) * duration
            pace_minutes = int(pace_sec // 60)
            pace_seconds = int(round(pace_sec - pace_minutes * 60))
            if pace_seconds == 60:
                pace_minutes += 1
                pace_seconds = 0
            pace_str = f"{pace_minutes}:{pace_seconds:02d}"
        avg_hr = act.get("averageHR")
        return PersonalRecord(
            distance_label=label,
            activity_id=str(act.get("activityId", "")),
            date=(act.get("startTimeLocal") or "")[:10] or "",
            distance_km=round(distance / 1000, 2),
            duration_hms=_format_duration(duration) or "",
            pace_min_per_km=pace_str,
            average_hr=int(avg_hr) if isinstance(avg_hr, (int, float)) else None,
        )

    def _longest_run_record(self, activities: list[dict]) -> PersonalRecord | None:
        longest: dict | None = None
        longest_distance = 0.0
        for act in activities:
            if _type_key(act) not in RUN_TYPES:
                continue
            distance = act.get("distance")
            if isinstance(distance, (int, float)) and distance > longest_distance:
                longest_distance = distance
                longest = act
        if longest is None:
            return None
        duration = longest.get("duration")
        avg_hr = longest.get("averageHR")
        distance = longest["distance"]
        pace_str: str | None = None
        if distance and duration and duration > 0:
            pace_sec = (1000 / distance) * duration
            pace_minutes = int(pace_sec // 60)
            pace_seconds = int(round(pace_sec - pace_minutes * 60))
            if pace_seconds == 60:
                pace_minutes += 1
                pace_seconds = 0
            pace_str = f"{pace_minutes}:{pace_seconds:02d}"
        return PersonalRecord(
            distance_label="longest_run",
            activity_id=str(longest.get("activityId", "")),
            date=(longest.get("startTimeLocal") or "")[:10] or "",
            distance_km=round(distance / 1000, 2),
            duration_hms=_format_duration(duration) or "",
            pace_min_per_km=pace_str,
            average_hr=int(avg_hr) if isinstance(avg_hr, (int, float)) else None,
        )
