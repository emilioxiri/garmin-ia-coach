"""Tests for MemoryRepository."""

from __future__ import annotations


def _repo(memory_db):
    from garmin_coach.infrastructure.db.memory_repository import MemoryRepository

    return MemoryRepository(memory_db)


def test_add_inserts_note(memory_db):
    repo = _repo(memory_db)
    repo.add("rodilla derecha molesta")
    rows = repo.all()
    assert len(rows) == 1
    assert rows[0]["note"] == "rodilla derecha molesta"


def test_add_stores_created_at(memory_db):
    repo = _repo(memory_db)
    repo.add("test")
    rows = repo.all()
    assert "created_at" in rows[0]
    assert rows[0]["created_at"]


def test_add_with_custom_timestamp(memory_db):
    repo = _repo(memory_db)
    repo.add("note", timestamp="2024-01-01T00:00:00+00:00")
    rows = repo.all()
    assert rows[0]["created_at"] == "2024-01-01T00:00:00+00:00"


def test_add_multiple_appends(memory_db):
    repo = _repo(memory_db)
    repo.add("nota 1")
    repo.add("nota 2")
    assert repo.count() == 2


def test_search_case_insensitive(memory_db):
    repo = _repo(memory_db)
    repo.add("Rodilla Derecha molesta")
    results = repo.search("rodilla")
    assert len(results) == 1


def test_search_substring(memory_db):
    repo = _repo(memory_db)
    repo.add("lesión en el tendón de Aquiles")
    results = repo.search("tendón")
    assert len(results) == 1


def test_search_no_match_returns_empty(memory_db):
    repo = _repo(memory_db)
    repo.add("rodilla")
    results = repo.search("hombro")
    assert results == []


def test_search_empty_query_returns_all(memory_db):
    repo = _repo(memory_db)
    repo.add("rodilla")
    repo.add("hombro")
    results = repo.search("")
    assert len(results) == 2


def test_search_limit(memory_db):
    repo = _repo(memory_db)
    for i in range(20):
        repo.add(f"nota {i}", timestamp=f"2024-01-{i + 1:02d}T00:00:00+00:00")
    results = repo.search("", limit=5)
    assert len(results) == 5


def test_search_sorted_by_created_at_desc(memory_db):
    repo = _repo(memory_db)
    repo.add("old", timestamp="2024-01-01T00:00:00+00:00")
    repo.add("new", timestamp="2024-06-01T00:00:00+00:00")
    results = repo.search("")
    assert results[0]["note"] == "new"
