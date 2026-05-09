"""
infrastructure/db/wellness_repository.py
Repositories for daily wellness tables: Sleep, HRV, BodyBattery,
TrainingReadiness, TrainingStatus, Respiration, SPO2, Stress.
"""

from __future__ import annotations

from datetime import date, timedelta

from tinydb import TinyDB

from garmin_coach.infrastructure.db.base_repository import BaseRepository


class _DateKeyedRepository(BaseRepository):
    """Base for all wellness repos keyed by 'date'."""

    def __init__(self, db: TinyDB, table_name: str) -> None:
        super().__init__(db, table_name, primary_key="date")

    def window(self, days: int) -> list[dict]:
        cutoff = (date.today() - timedelta(days=max(1, days))).isoformat()
        rows = self.find_by_date_range("date", cutoff, date.today().isoformat())
        rows.sort(key=lambda r: r.get("date", ""), reverse=True)
        return rows


class SleepRepository(_DateKeyedRepository):
    def __init__(self, db: TinyDB) -> None:
        super().__init__(db, "sleep")


class HRVRepository(_DateKeyedRepository):
    def __init__(self, db: TinyDB) -> None:
        super().__init__(db, "hrv")


class BodyBatteryRepository(_DateKeyedRepository):
    def __init__(self, db: TinyDB) -> None:
        super().__init__(db, "body_battery")


class TrainingReadinessRepository(_DateKeyedRepository):
    def __init__(self, db: TinyDB) -> None:
        super().__init__(db, "training_readiness")


class TrainingStatusRepository(_DateKeyedRepository):
    def __init__(self, db: TinyDB) -> None:
        super().__init__(db, "training_status")


class RespirationRepository(_DateKeyedRepository):
    def __init__(self, db: TinyDB) -> None:
        super().__init__(db, "respiration")


class SPO2Repository(_DateKeyedRepository):
    def __init__(self, db: TinyDB) -> None:
        super().__init__(db, "spo2")


class StressRepository(_DateKeyedRepository):
    def __init__(self, db: TinyDB) -> None:
        super().__init__(db, "stress")
