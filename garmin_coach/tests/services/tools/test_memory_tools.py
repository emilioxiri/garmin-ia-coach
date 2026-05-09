"""Tests for services/tools/memory_tools.py."""

from tinydb import TinyDB
from tinydb.storages import MemoryStorage

from garmin_coach.infrastructure.db.memory_repository import MemoryRepository
from garmin_coach.services.tools.memory_tools import SearchMemoryTool


def _make_repo(notes: list[str] | None = None):
    db = TinyDB(storage=MemoryStorage)
    repo = MemoryRepository(db)
    for note in notes or []:
        repo.add(note)
    return repo


def test_search_memory_empty():
    repo = _make_repo()
    result = SearchMemoryTool(repo).handle(query="anything")
    assert result.data == []


def test_search_memory_no_query_returns_all():
    repo = _make_repo(["lesión rodilla", "buen día"])
    result = SearchMemoryTool(repo).handle(query="")
    assert len(result.data) == 2


def test_search_memory_filters_by_substring():
    repo = _make_repo(["lesión rodilla derecha", "buen día de entrenamiento"])
    result = SearchMemoryTool(repo).handle(query="lesión")
    assert len(result.data) == 1
    assert "lesión" in result.data[0]["note"]


def test_search_memory_case_insensitive():
    repo = _make_repo(["Lesión Rodilla"])
    result = SearchMemoryTool(repo).handle(query="lesión")
    assert len(result.data) == 1


def test_search_memory_limit():
    repo = _make_repo([f"note {i}" for i in range(20)])
    result = SearchMemoryTool(repo).handle(limit=5)
    assert len(result.data) == 5


def test_search_memory_no_match():
    repo = _make_repo(["running suave", "padel"])
    result = SearchMemoryTool(repo).handle(query="yoga")
    assert result.data == []
