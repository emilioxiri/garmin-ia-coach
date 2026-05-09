"""Tests for TinyDBFactory."""

from __future__ import annotations

from tinydb import TinyDB


def test_factory_creates_instance(tmp_path):
    from garmin_coach.infrastructure.db.tinydb_factory import TinyDBFactory

    factory = TinyDBFactory(tmp_path / "test.json")
    db = factory.get()
    assert isinstance(db, TinyDB)


def test_factory_returns_same_instance(tmp_path):
    from garmin_coach.infrastructure.db.tinydb_factory import TinyDBFactory

    factory = TinyDBFactory(tmp_path / "test.json")
    db1 = factory.get()
    db2 = factory.get()
    assert db1 is db2


def test_factory_creates_parent_dirs(tmp_path):
    from garmin_coach.infrastructure.db.tinydb_factory import TinyDBFactory

    deep = tmp_path / "a" / "b" / "c" / "test.json"
    factory = TinyDBFactory(deep)
    factory.get()
    assert deep.exists()


def test_factory_close_resets_instance(tmp_path):
    from garmin_coach.infrastructure.db.tinydb_factory import TinyDBFactory

    factory = TinyDBFactory(tmp_path / "test.json")
    db1 = factory.get()
    factory.close()
    db2 = factory.get()
    assert db1 is not db2


def test_factory_close_idempotent(tmp_path):
    from garmin_coach.infrastructure.db.tinydb_factory import TinyDBFactory

    factory = TinyDBFactory(tmp_path / "test.json")
    factory.get()
    factory.close()
    factory.close()  # should not raise
