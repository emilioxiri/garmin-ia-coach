"""Tests for BaseRepository."""

from __future__ import annotations

import pytest


def test_all_empty(memory_db):
    from garmin_coach.infrastructure.db.base_repository import BaseRepository

    repo = BaseRepository(memory_db, "items", primary_key="id")
    assert repo.all() == []


def test_count_empty(memory_db):
    from garmin_coach.infrastructure.db.base_repository import BaseRepository

    repo = BaseRepository(memory_db, "items", primary_key="id")
    assert repo.count() == 0


def test_is_empty_true(memory_db):
    from garmin_coach.infrastructure.db.base_repository import BaseRepository

    repo = BaseRepository(memory_db, "items", primary_key="id")
    assert repo.is_empty() is True


def test_insert_and_all(memory_db):
    from garmin_coach.infrastructure.db.base_repository import BaseRepository

    repo = BaseRepository(memory_db, "items", primary_key=None)
    repo.insert({"note": "hello"})
    repo.insert({"note": "world"})
    assert len(repo.all()) == 2


def test_is_empty_false_after_insert(memory_db):
    from garmin_coach.infrastructure.db.base_repository import BaseRepository

    repo = BaseRepository(memory_db, "items", primary_key=None)
    repo.insert({"x": 1})
    assert repo.is_empty() is False


def test_count_after_inserts(memory_db):
    from garmin_coach.infrastructure.db.base_repository import BaseRepository

    repo = BaseRepository(memory_db, "items", primary_key=None)
    repo.insert({"x": 1})
    repo.insert({"x": 2})
    assert repo.count() == 2


def test_upsert_inserts_new(memory_db):
    from garmin_coach.infrastructure.db.base_repository import BaseRepository

    repo = BaseRepository(memory_db, "items", primary_key="id")
    repo.upsert({"id": "a", "value": 1})
    assert repo.count() == 1


def test_upsert_updates_existing(memory_db):
    from garmin_coach.infrastructure.db.base_repository import BaseRepository

    repo = BaseRepository(memory_db, "items", primary_key="id")
    repo.upsert({"id": "a", "value": 1})
    repo.upsert({"id": "a", "value": 2})
    rows = repo.all()
    assert len(rows) == 1
    assert rows[0]["value"] == 2


def test_upsert_requires_primary_key(memory_db):
    from garmin_coach.infrastructure.db.base_repository import BaseRepository

    repo = BaseRepository(memory_db, "items", primary_key=None)
    with pytest.raises(RuntimeError, match="primary_key"):
        repo.upsert({"x": 1})


def test_upsert_many_returns_count(memory_db):
    from garmin_coach.infrastructure.db.base_repository import BaseRepository

    repo = BaseRepository(memory_db, "items", primary_key="id")
    records = [{"id": str(i), "v": i} for i in range(5)]
    count = repo.upsert_many(records)
    assert count == 5
    assert repo.count() == 5


def test_upsert_many_requires_primary_key(memory_db):
    from garmin_coach.infrastructure.db.base_repository import BaseRepository

    repo = BaseRepository(memory_db, "items", primary_key=None)
    with pytest.raises(RuntimeError, match="primary_key"):
        repo.upsert_many([{"x": 1}])


def test_find_by_date_range(memory_db):
    from garmin_coach.infrastructure.db.base_repository import BaseRepository

    repo = BaseRepository(memory_db, "items", primary_key="date")
    repo.upsert({"date": "2024-01-01", "v": 1})
    repo.upsert({"date": "2024-01-10", "v": 2})
    repo.upsert({"date": "2024-01-20", "v": 3})
    rows = repo.find_by_date_range("date", "2024-01-05", "2024-01-15")
    assert len(rows) == 1
    assert rows[0]["v"] == 2


def test_find_by_date_range_inclusive(memory_db):
    from garmin_coach.infrastructure.db.base_repository import BaseRepository

    repo = BaseRepository(memory_db, "items", primary_key="date")
    repo.upsert({"date": "2024-01-01"})
    repo.upsert({"date": "2024-01-10"})
    rows = repo.find_by_date_range("date", "2024-01-01", "2024-01-01")
    assert len(rows) == 1


def test_delete_older_than(memory_db):
    from garmin_coach.infrastructure.db.base_repository import BaseRepository

    repo = BaseRepository(memory_db, "items", primary_key="date")
    repo.upsert({"date": "2024-01-01"})
    repo.upsert({"date": "2024-01-10"})
    repo.upsert({"date": "2024-01-20"})
    removed = repo.delete_older_than("date", "2024-01-10")
    assert removed == 1
    rows = repo.all()
    assert len(rows) == 2
    dates = {r["date"] for r in rows}
    assert "2024-01-01" not in dates


def test_delete_older_than_nothing_to_remove(memory_db):
    from garmin_coach.infrastructure.db.base_repository import BaseRepository

    repo = BaseRepository(memory_db, "items", primary_key="date")
    repo.upsert({"date": "2024-01-20"})
    removed = repo.delete_older_than("date", "2024-01-01")
    assert removed == 0
    assert repo.count() == 1


def test_latest(memory_db):
    from garmin_coach.infrastructure.db.base_repository import BaseRepository

    repo = BaseRepository(memory_db, "items", primary_key="date")
    repo.upsert({"date": "2024-01-01", "v": 1})
    repo.upsert({"date": "2024-01-20", "v": 3})
    repo.upsert({"date": "2024-01-10", "v": 2})
    latest = repo.latest("date")
    assert latest["v"] == 3


def test_latest_empty_returns_none(memory_db):
    from garmin_coach.infrastructure.db.base_repository import BaseRepository

    repo = BaseRepository(memory_db, "items")
    assert repo.latest("date") is None
