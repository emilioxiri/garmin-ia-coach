"""
domain/fitness.py
Fitness snapshot and personal records dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FitnessMetrics:
    payload: dict

    @classmethod
    def from_dict(cls, d: dict) -> "FitnessMetrics":
        return cls(payload=dict(d))

    def as_dict(self) -> dict:
        return dict(self.payload)


@dataclass(frozen=True, slots=True)
class RacePredictions:
    payload: dict

    @classmethod
    def from_dict(cls, d: dict) -> "RacePredictions":
        return cls(payload=dict(d))

    def as_dict(self) -> dict:
        return dict(self.payload)


@dataclass(frozen=True, slots=True)
class LactateThreshold:
    payload: dict

    @classmethod
    def from_dict(cls, d: dict) -> "LactateThreshold":
        return cls(payload=dict(d))

    def as_dict(self) -> dict:
        return dict(self.payload)


@dataclass(frozen=True, slots=True)
class EnduranceScore:
    payload: dict

    @classmethod
    def from_dict(cls, d: dict) -> "EnduranceScore":
        return cls(payload=dict(d))

    def as_dict(self) -> dict:
        return dict(self.payload)


@dataclass(frozen=True, slots=True)
class PersonalRecord:
    """Best known result for a canonical race distance."""

    distance_label: str
    activity_id: str
    date: str
    distance_km: float
    duration_hms: str
    pace_min_per_km: str | None
    average_hr: int | None
