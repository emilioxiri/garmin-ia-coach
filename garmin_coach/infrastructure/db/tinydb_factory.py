"""
infrastructure/db/tinydb_factory.py
Single point of truth for TinyDB instance creation.
"""

from __future__ import annotations

from pathlib import Path

from tinydb import TinyDB


class TinyDBFactory:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._instance: TinyDB | None = None

    def get(self) -> TinyDB:
        if self._instance is None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._instance = TinyDB(self._db_path, indent=2, ensure_ascii=False)
        return self._instance

    def close(self) -> None:
        if self._instance is not None:
            self._instance.close()
            self._instance = None
