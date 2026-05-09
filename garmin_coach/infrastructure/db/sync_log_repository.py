"""
infrastructure/db/sync_log_repository.py
Repository for sync run audit log (append-only).
"""

from __future__ import annotations

from datetime import datetime, timezone

from tinydb import TinyDB

from garmin_coach.infrastructure.db.base_repository import BaseRepository


class SyncLogRepository(BaseRepository):
    def __init__(self, db: TinyDB) -> None:
        super().__init__(db, "sync_log", primary_key=None)

    def log(self, summary: dict, started_at: str | None = None) -> None:
        synced_at = started_at or datetime.now(timezone.utc).isoformat()
        self.insert({"synced_at": synced_at, "summary": summary})

    def last_sync(self) -> str | None:
        records = self.all()
        if not records:
            return None
        latest = max(records, key=lambda r: r.get("synced_at", ""))
        return latest.get("synced_at")
