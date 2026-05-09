"""
infrastructure/db/base_repository.py
Generic TinyDB repository base class.
"""

from __future__ import annotations

from typing import Iterable

from tinydb import TinyDB


class BaseRepository:
    """Generic TinyDB repository.

    primary_key: unique field name (e.g. 'activityId' or 'date').
    If None the table is append-only — upsert() is not available.
    """

    def __init__(
        self, db: TinyDB, table_name: str, primary_key: str | None = None
    ) -> None:
        self._db = db
        self._table_name = table_name
        self._primary_key = primary_key

    @property
    def _table(self):
        return self._db.table(self._table_name)

    def all(self) -> list[dict]:
        return self._table.all()

    def count(self) -> int:
        return len(self._table)

    def is_empty(self) -> bool:
        return self.count() == 0

    def upsert(self, record: dict) -> None:
        if self._primary_key is None:
            raise RuntimeError("upsert requires a primary_key")
        from tinydb import Query

        Q = Query()
        key_value = record[self._primary_key]
        self._table.upsert(record, Q[self._primary_key] == key_value)

    def upsert_many(self, records: Iterable[dict]) -> int:
        if self._primary_key is None:
            raise RuntimeError("upsert_many requires a primary_key")
        count = 0
        for record in records:
            self.upsert(record)
            count += 1
        return count

    def insert(self, record: dict) -> None:
        self._table.insert(record)

    def find_by_date_range(
        self, date_field: str, start_iso: str, end_iso: str
    ) -> list[dict]:
        from tinydb import Query

        Q = Query()
        return self._table.search(
            Q[date_field].test(lambda v: bool(v) and start_iso <= v <= end_iso)
        )

    def delete_older_than(self, date_field: str, cutoff_iso: str) -> int:
        from tinydb import Query

        Q = Query()
        old = self._table.search(Q[date_field] < cutoff_iso)
        count = len(old)
        if count:
            self._table.remove(Q[date_field] < cutoff_iso)
        return count

    def latest(self, date_field: str) -> dict | None:
        records = self._table.all()
        if not records:
            return None
        return max(records, key=lambda r: r.get(date_field, ""))
