"""
infrastructure/db/fitness_repository.py
Repositories for fitness snapshot tables (single-row, replaced on each sync).
"""

from __future__ import annotations

from tinydb import TinyDB

from garmin_coach.infrastructure.db.base_repository import BaseRepository


class _SnapshotRepository(BaseRepository):
    """Append-only snapshot table with a replace() helper."""

    def __init__(self, db: TinyDB, table_name: str) -> None:
        super().__init__(db, table_name, primary_key=None)

    def replace(self, record: dict) -> None:
        """Replace the entire table with a single record (truncate + insert)."""
        self._table.truncate()
        self._table.insert(record)

    def latest(self, date_field: str = "date") -> dict | None:  # type: ignore[override]
        """Return the most recent record or None."""
        records = self._table.all()
        if not records:
            return None
        return max(records, key=lambda r: r.get(date_field, ""))


class FitnessMetricsRepository(_SnapshotRepository):
    def __init__(self, db: TinyDB) -> None:
        super().__init__(db, "fitness_metrics")


class RacePredictionsRepository(_SnapshotRepository):
    def __init__(self, db: TinyDB) -> None:
        super().__init__(db, "race_predictions")


class LactateThresholdRepository(_SnapshotRepository):
    def __init__(self, db: TinyDB) -> None:
        super().__init__(db, "lactate_threshold")


class EnduranceScoreRepository(_SnapshotRepository):
    def __init__(self, db: TinyDB) -> None:
        super().__init__(db, "endurance_score")
