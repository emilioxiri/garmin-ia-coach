"""
domain/wellness.py
Wellness daily dataclasses: Sleep, HRV, BodyBattery, TrainingReadiness,
TrainingStatus, Respiration, SPO2, Stress.

Each holds a `date` key and a `payload` dict for lossless TinyDB round-trips.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Sleep:
    date: str
    payload: dict

    @classmethod
    def from_dict(cls, d: dict) -> "Sleep":
        return cls(date=d.get("date", ""), payload=dict(d))

    def as_dict(self) -> dict:
        return dict(self.payload)


@dataclass(frozen=True, slots=True)
class HRV:
    date: str
    payload: dict

    @classmethod
    def from_dict(cls, d: dict) -> "HRV":
        return cls(date=d.get("date", ""), payload=dict(d))

    def as_dict(self) -> dict:
        return dict(self.payload)


@dataclass(frozen=True, slots=True)
class BodyBattery:
    date: str
    payload: dict

    @classmethod
    def from_dict(cls, d: dict) -> "BodyBattery":
        return cls(date=d.get("date", ""), payload=dict(d))

    def as_dict(self) -> dict:
        return dict(self.payload)


@dataclass(frozen=True, slots=True)
class TrainingReadiness:
    date: str
    payload: dict

    @classmethod
    def from_dict(cls, d: dict) -> "TrainingReadiness":
        return cls(date=d.get("date", ""), payload=dict(d))

    def as_dict(self) -> dict:
        return dict(self.payload)


@dataclass(frozen=True, slots=True)
class TrainingStatus:
    date: str
    payload: dict

    @classmethod
    def from_dict(cls, d: dict) -> "TrainingStatus":
        return cls(date=d.get("date", ""), payload=dict(d))

    def as_dict(self) -> dict:
        return dict(self.payload)


@dataclass(frozen=True, slots=True)
class Respiration:
    date: str
    payload: dict

    @classmethod
    def from_dict(cls, d: dict) -> "Respiration":
        return cls(date=d.get("date", ""), payload=dict(d))

    def as_dict(self) -> dict:
        return dict(self.payload)


@dataclass(frozen=True, slots=True)
class SPO2:
    date: str
    payload: dict

    @classmethod
    def from_dict(cls, d: dict) -> "SPO2":
        return cls(date=d.get("date", ""), payload=dict(d))

    def as_dict(self) -> dict:
        return dict(self.payload)


@dataclass(frozen=True, slots=True)
class Stress:
    date: str
    payload: dict

    @classmethod
    def from_dict(cls, d: dict) -> "Stress":
        return cls(date=d.get("date", ""), payload=dict(d))

    def as_dict(self) -> dict:
        return dict(self.payload)
