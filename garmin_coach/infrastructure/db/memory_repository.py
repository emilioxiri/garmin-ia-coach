"""
infrastructure/db/memory_repository.py
Repository for coach memory notes (append-only).
"""

from __future__ import annotations

from datetime import datetime, timezone

from tinydb import TinyDB

from garmin_coach.infrastructure.db.base_repository import BaseRepository


class MemoryRepository(BaseRepository):
    def __init__(self, db: TinyDB) -> None:
        super().__init__(db, "memory", primary_key=None)

    def add(self, note: str, timestamp: str | None = None) -> None:
        created_at = timestamp or datetime.now(timezone.utc).isoformat()
        self.insert({"note": note, "created_at": created_at})

    def search(self, query: str, limit: int = 10) -> list[dict]:
        rows = self.all()
        needle = (query or "").strip().lower()
        if needle:
            rows = [r for r in rows if needle in (r.get("note") or "").lower()]
        rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        cap = max(1, min(int(limit), 50))
        return rows[:cap]
