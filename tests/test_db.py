"""Unit tests for db.py — all functions."""

import pytest
from datetime import date, timedelta
from tinydb import TinyDB
from tinydb.storages import MemoryStorage
from unittest.mock import patch


def make_db():
    return TinyDB(storage=MemoryStorage)


def patch_db(db_instance):
    return patch("db._db_instance", db_instance)


# ── is_db_empty ───────────────────────────────────────────────────────────────

def test_is_db_empty_true_when_no_data():
    import db
    db_inst = make_db()
    with patch_db(db_inst):
        assert db.is_db_empty() is True


def test_is_db_empty_false_when_has_activity():
    import db
    db_inst = make_db()
    db_inst.table("activities").insert({"activityId": "1", "startTimeLocal": "2024-01-01 10:00:00"})
    with patch_db(db_inst):
        assert db.is_db_empty() is False


def test_is_db_empty_false_when_has_sleep():
    import db
    db_inst = make_db()
    db_inst.table("sleep").insert({"date": "2024-01-01"})
    with patch_db(db_inst):
        assert db.is_db_empty() is False


# ── get_last_date_in_db ───────────────────────────────────────────────────────

def test_get_last_date_in_db_none_when_empty():
    import db
    db_inst = make_db()
    with patch_db(db_inst):
        assert db.get_last_date_in_db() is None


def test_get_last_date_in_db_from_activities():
    import db
    db_inst = make_db()
    db_inst.table("activities").insert({"startTimeLocal": "2024-01-10 08:00:00"})
    db_inst.table("activities").insert({"startTimeLocal": "2024-01-20 09:00:00"})
    with patch_db(db_inst):
        assert db.get_last_date_in_db() == "2024-01-20"


def test_get_last_date_in_db_from_sleep():
    import db
    db_inst = make_db()
    db_inst.table("sleep").insert({"date": "2024-01-15"})
    db_inst.table("sleep").insert({"date": "2024-01-22"})
    with patch_db(db_inst):
        assert db.get_last_date_in_db() == "2024-01-22"


def test_get_last_date_in_db_max_across_tables():
    import db
    db_inst = make_db()
    db_inst.table("activities").insert({"startTimeLocal": "2024-01-20 10:00:00"})
    db_inst.table("sleep").insert({"date": "2024-01-18"})
    db_inst.table("hrv").insert({"date": "2024-01-25"})
    db_inst.table("body_battery").insert({"date": "2024-01-22"})
    with patch_db(db_inst):
        assert db.get_last_date_in_db() == "2024-01-25"


def test_get_last_date_in_db_skips_empty_fields():
    import db
    db_inst = make_db()
    db_inst.table("activities").insert({"startTimeLocal": ""})
    db_inst.table("sleep").insert({"date": "2024-01-10"})
    with patch_db(db_inst):
        assert db.get_last_date_in_db() == "2024-01-10"


# ── purge_old_data ────────────────────────────────────────────────────────────

def test_purge_removes_old_activities():
    import db
    db_inst = make_db()
    cutoff = date.today() - timedelta(days=30)
    old_date = (cutoff - timedelta(days=1)).isoformat()
    recent_date = (cutoff + timedelta(days=1)).isoformat()
    db_inst.table("activities").insert({"activityId": "old", "startTimeLocal": f"{old_date} 10:00:00"})
    db_inst.table("activities").insert({"activityId": "recent", "startTimeLocal": f"{recent_date} 10:00:00"})
    with patch_db(db_inst):
        db.purge_old_data(days=30)
        remaining = db_inst.table("activities").all()
    assert len(remaining) == 1
    assert remaining[0]["activityId"] == "recent"


def test_purge_removes_old_sleep():
    import db
    db_inst = make_db()
    cutoff = date.today() - timedelta(days=30)
    old_date = (cutoff - timedelta(days=1)).isoformat()
    recent_date = (cutoff + timedelta(days=1)).isoformat()
    db_inst.table("sleep").insert({"date": old_date})
    db_inst.table("sleep").insert({"date": recent_date})
    with patch_db(db_inst):
        db.purge_old_data(days=30)
        remaining = db_inst.table("sleep").all()
    assert len(remaining) == 1
    assert remaining[0]["date"] == recent_date


def test_purge_removes_old_hrv_and_body_battery():
    import db
    db_inst = make_db()
    cutoff = date.today() - timedelta(days=30)
    old_date = (cutoff - timedelta(days=5)).isoformat()
    recent_date = date.today().isoformat()
    for table_name in ("hrv", "body_battery"):
        db_inst.table(table_name).insert({"date": old_date})
        db_inst.table(table_name).insert({"date": recent_date})
    with patch_db(db_inst):
        db.purge_old_data(days=30)
    for table_name in ("hrv", "body_battery"):
        remaining = db_inst.table(table_name).all()
        assert len(remaining) == 1
        assert remaining[0]["date"] == recent_date


def test_purge_keeps_cutoff_date_itself():
    import db
    db_inst = make_db()
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    db_inst.table("sleep").insert({"date": cutoff})
    with patch_db(db_inst):
        db.purge_old_data(days=30)
        remaining = db_inst.table("sleep").all()
    assert len(remaining) == 1


def test_purge_returns_removed_counts():
    import db
    db_inst = make_db()
    cutoff = date.today() - timedelta(days=30)
    old_date = (cutoff - timedelta(days=1)).isoformat()
    db_inst.table("activities").insert({"activityId": "a1", "startTimeLocal": f"{old_date} 10:00:00"})
    db_inst.table("activities").insert({"activityId": "a2", "startTimeLocal": f"{old_date} 11:00:00"})
    db_inst.table("sleep").insert({"date": old_date})
    with patch_db(db_inst):
        removed = db.purge_old_data(days=30)
    assert removed["activities"] == 2
    assert removed["sleep"] == 1
    assert removed["hrv"] == 0
    assert removed["body_battery"] == 0


def test_purge_empty_db_returns_zeros():
    import db
    db_inst = make_db()
    with patch_db(db_inst):
        removed = db.purge_old_data(days=30)
    assert all(v == 0 for v in removed.values())


# ── get_context_for_ai ────────────────────────────────────────────────────────

def test_get_context_for_ai_returns_all_keys():
    import db
    db_inst = make_db()
    with patch_db(db_inst):
        ctx = db.get_context_for_ai(days=7)
    assert set(ctx.keys()) == {"activities", "sleep", "hrv", "body_battery", "memory", "days_covered"}
    assert ctx["days_covered"] == 7


def test_get_context_for_ai_filters_old_activities():
    import db
    db_inst = make_db()
    cutoff = date.today() - timedelta(days=7)
    old = (cutoff - timedelta(days=1)).isoformat()
    recent = date.today().isoformat()
    db_inst.table("activities").insert({"activityId": "old", "startTimeLocal": f"{old} 08:00:00"})
    db_inst.table("activities").insert({"activityId": "new", "startTimeLocal": f"{recent} 08:00:00"})
    with patch_db(db_inst):
        ctx = db.get_context_for_ai(days=7)
    assert len(ctx["activities"]) == 1
    assert ctx["activities"][0]["activityId"] == "new"


def test_get_context_for_ai_caps_at_20_activities():
    import db
    db_inst = make_db()
    today = date.today().isoformat()
    for i in range(25):
        db_inst.table("activities").insert({"activityId": str(i), "startTimeLocal": f"{today} {i:02d}:00:00"})
    with patch_db(db_inst):
        ctx = db.get_context_for_ai(days=7)
    assert len(ctx["activities"]) == 20


def test_get_context_for_ai_activities_sorted_descending():
    import db
    db_inst = make_db()
    today = date.today()
    for i in range(3):
        d = (today - timedelta(days=i)).isoformat()
        db_inst.table("activities").insert({"activityId": str(i), "startTimeLocal": f"{d} 08:00:00"})
    with patch_db(db_inst):
        ctx = db.get_context_for_ai(days=7)
    times = [a["startTimeLocal"] for a in ctx["activities"]]
    assert times == sorted(times, reverse=True)


def test_get_context_for_ai_includes_all_memory():
    import db
    db_inst = make_db()
    db_inst.table("memory").insert({"note": "rodilla derecha", "created_at": "2020-01-01"})
    db_inst.table("memory").insert({"note": "lesión antigua", "created_at": "2019-01-01"})
    with patch_db(db_inst):
        ctx = db.get_context_for_ai(days=7)
    assert len(ctx["memory"]) == 2


def test_get_context_for_ai_filters_sleep_hrv_bb():
    import db
    db_inst = make_db()
    cutoff = date.today() - timedelta(days=7)
    old = (cutoff - timedelta(days=1)).isoformat()
    recent = date.today().isoformat()
    for table in ("sleep", "hrv", "body_battery"):
        db_inst.table(table).insert({"date": old, "value": "old"})
        db_inst.table(table).insert({"date": recent, "value": "new"})
    with patch_db(db_inst):
        ctx = db.get_context_for_ai(days=7)
    for key in ("sleep", "hrv", "body_battery"):
        assert len(ctx[key]) == 1
        assert ctx[key][0]["value"] == "new"


# ── save_memory ───────────────────────────────────────────────────────────────

def test_save_memory_inserts_note():
    import db
    db_inst = make_db()
    with patch_db(db_inst):
        db.save_memory("rodilla derecha molesta")
    records = db_inst.table("memory").all()
    assert len(records) == 1
    assert records[0]["note"] == "rodilla derecha molesta"


def test_save_memory_stores_created_at():
    import db
    db_inst = make_db()
    with patch_db(db_inst):
        db.save_memory("test note")
    record = db_inst.table("memory").all()[0]
    assert "created_at" in record
    assert record["created_at"]  # non-empty


def test_save_memory_multiple_notes_append():
    import db
    db_inst = make_db()
    with patch_db(db_inst):
        db.save_memory("nota 1")
        db.save_memory("nota 2")
    assert len(db_inst.table("memory").all()) == 2


# ── get_last_sync / log_sync ──────────────────────────────────────────────────

def test_get_last_sync_none_when_empty():
    import db
    db_inst = make_db()
    with patch_db(db_inst):
        assert db.get_last_sync() is None


def test_get_last_sync_returns_latest():
    import db
    db_inst = make_db()
    db_inst.table("sync_log").insert({"synced_at": "2024-01-10T08:00:00", "summary": {}})
    db_inst.table("sync_log").insert({"synced_at": "2024-01-20T08:00:00", "summary": {}})
    db_inst.table("sync_log").insert({"synced_at": "2024-01-15T08:00:00", "summary": {}})
    with patch_db(db_inst):
        result = db.get_last_sync()
    assert result == "2024-01-20T08:00:00"


def test_log_sync_inserts_record():
    import db
    db_inst = make_db()
    summary = {"activities": 5, "sleep": 3}
    with patch_db(db_inst):
        db.log_sync(summary)
    records = db_inst.table("sync_log").all()
    assert len(records) == 1
    assert records[0]["summary"] == summary


def test_log_sync_stores_synced_at():
    import db
    db_inst = make_db()
    with patch_db(db_inst):
        db.log_sync({})
    record = db_inst.table("sync_log").all()[0]
    assert "synced_at" in record
    assert record["synced_at"]
