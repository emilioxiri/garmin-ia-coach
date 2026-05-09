"""Shared fixtures for infrastructure/db tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from tinydb import TinyDB
from tinydb.storages import MemoryStorage


@pytest.fixture
def memory_db() -> Iterator[TinyDB]:
    db = TinyDB(storage=MemoryStorage)
    yield db
    db.close()
