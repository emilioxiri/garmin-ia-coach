"""
domain/activity.py
Activity entity and ActivityType enum.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ActivityType(StrEnum):
    RUNNING = "running"
    TRAIL_RUNNING = "trail_running"
    TREADMILL_RUNNING = "treadmill_running"
    VIRTUAL_RUN = "virtual_run"
    TRACK_RUNNING = "track_running"
    INDOOR_RUNNING = "indoor_running"
    STREET_RUNNING = "street_running"
    CYCLING = "cycling"
    SWIMMING = "swimming"
    STRENGTH_TRAINING = "strength_training"
    INDOOR_STRENGTH_TRAINING = "indoor_strength_training"
    YOGA = "yoga"
    PILATES = "pilates"
    PADEL = "padel"
    TENNIS = "tennis"
    PICKLEBALL = "pickleball"
    SQUASH = "squash"
    RACQUET_BALL = "racquet_ball"
    RACQUETBALL = "racquetball"
    TABLE_TENNIS = "table_tennis"
    BADMINTON = "badminton"
    BOXING = "boxing"
    MIXED_MARTIAL_ARTS = "mixed_martial_arts"
    INDOOR_CLIMBING = "indoor_climbing"
    BOULDERING = "bouldering"
    ROCK_CLIMBING = "rock_climbing"
    HIIT = "hiit"
    CARDIO = "cardio"
    STRETCHING = "stretching"
    BREATHWORK = "breathwork"
    MEDITATION = "meditation"
    MOBILITY = "mobility"
    GYM = "gym"
    FLOOR_CLIMBING = "floor_climbing"
    STAIR_CLIMBING = "stair_climbing"
    WALKING = "walking"
    HIKING = "hiking"
    OTHER = "other"

    def is_run(self) -> bool:
        return self in _RUN_TYPE_SET

    def is_distance_based(self) -> bool:
        return self not in _NON_DISTANCE_TYPE_SET


# Sets derived from enum values for fast membership checks.
_RUN_TYPE_SET: frozenset[ActivityType] = frozenset(
    [
        ActivityType.RUNNING,
        ActivityType.TRAIL_RUNNING,
        ActivityType.TREADMILL_RUNNING,
        ActivityType.VIRTUAL_RUN,
        ActivityType.TRACK_RUNNING,
        ActivityType.INDOOR_RUNNING,
        ActivityType.STREET_RUNNING,
    ]
)

_NON_DISTANCE_TYPE_SET: frozenset[ActivityType] = frozenset(
    [
        ActivityType.PADEL,
        ActivityType.TENNIS,
        ActivityType.PICKLEBALL,
        ActivityType.SQUASH,
        ActivityType.RACQUET_BALL,
        ActivityType.RACQUETBALL,
        ActivityType.TABLE_TENNIS,
        ActivityType.BADMINTON,
        ActivityType.BOXING,
        ActivityType.MIXED_MARTIAL_ARTS,
        ActivityType.STRENGTH_TRAINING,
        ActivityType.INDOOR_STRENGTH_TRAINING,
        ActivityType.YOGA,
        ActivityType.PILATES,
        ActivityType.INDOOR_CLIMBING,
        ActivityType.BOULDERING,
        ActivityType.ROCK_CLIMBING,
        ActivityType.HIIT,
        ActivityType.CARDIO,
        ActivityType.STRETCHING,
        ActivityType.BREATHWORK,
        ActivityType.MEDITATION,
        ActivityType.MOBILITY,
        ActivityType.GYM,
        ActivityType.FLOOR_CLIMBING,
        ActivityType.STAIR_CLIMBING,
    ]
)

# String sets for backward compatibility with context_builder.py and coach_tools.py.
RUN_TYPES: frozenset[str] = frozenset(t.value for t in _RUN_TYPE_SET)
NON_DISTANCE_TYPES: frozenset[str] = frozenset(t.value for t in _NON_DISTANCE_TYPE_SET)


@dataclass(frozen=True, slots=True)
class Activity:
    """Lightweight domain entity wrapping a Garmin activity record."""

    activity_id: str
    start_time_local: str
    activity_type: str
    distance_m: float | None
    duration_s: float | None
    average_hr: int | None
    max_hr: int | None
    payload: dict

    @classmethod
    def from_dict(cls, d: dict) -> "Activity":
        """Defensively construct an Activity from a raw TinyDB record."""
        activity_type = d.get("activityType")
        if isinstance(activity_type, dict):
            type_key = activity_type.get("typeKey") or "other"
        elif isinstance(activity_type, str):
            type_key = activity_type
        else:
            type_key = "other"

        distance = d.get("distance")
        duration = d.get("duration")
        avg_hr = d.get("averageHR")
        max_hr = d.get("maxHR")

        return cls(
            activity_id=str(d.get("activityId", "")),
            start_time_local=d.get("startTimeLocal") or d.get("startTime") or "",
            activity_type=type_key,
            distance_m=float(distance) if isinstance(distance, (int, float)) else None,
            duration_s=float(duration) if isinstance(duration, (int, float)) else None,
            average_hr=int(avg_hr) if isinstance(avg_hr, (int, float)) else None,
            max_hr=int(max_hr) if isinstance(max_hr, (int, float)) else None,
            payload=dict(d),
        )

    def as_dict(self) -> dict:
        """Return the full payload dict (lossless round-trip)."""
        return dict(self.payload)

    @property
    def date_iso(self) -> str | None:
        if self.start_time_local and len(self.start_time_local) >= 10:
            return self.start_time_local[:10]
        return None
