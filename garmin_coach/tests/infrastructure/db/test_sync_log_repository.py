"""Tests for SyncLogRepository."""

from __future__ import annotations


def _repo(memory_db):
    from garmin_coach.infrastructure.db.sync_log_repository import SyncLogRepository

    return SyncLogRepository(memory_db)


def test_last_sync_none_when_empty(memory_db):
    assert _repo(memory_db).last_sync() is None


def test_log_inserts_record(memory_db):
    repo = _repo(memory_db)
    summary = {"activities": 5, "sleep": 3}
    repo.log(summary)
    rows = repo.all()
    assert len(rows) == 1
    assert rows[0]["summary"] == summary


def test_log_stores_synced_at(memory_db):
    repo = _repo(memory_db)
    repo.log({})
    rows = repo.all()
    assert "synced_at" in rows[0]
    assert rows[0]["synced_at"]


def test_log_with_custom_started_at(memory_db):
    repo = _repo(memory_db)
    repo.log({}, started_at="2024-01-10T08:00:00+00:00")
    rows = repo.all()
    assert rows[0]["synced_at"] == "2024-01-10T08:00:00+00:00"


def test_last_sync_returns_latest(memory_db):
    repo = _repo(memory_db)
    repo.log({}, started_at="2024-01-10T08:00:00")
    repo.log({}, started_at="2024-01-20T08:00:00")
    repo.log({}, started_at="2024-01-15T08:00:00")
    assert repo.last_sync() == "2024-01-20T08:00:00"


def test_log_multiple_entries(memory_db):
    repo = _repo(memory_db)
    repo.log({"run": 1})
    repo.log({"run": 2})
    assert repo.count() == 2
