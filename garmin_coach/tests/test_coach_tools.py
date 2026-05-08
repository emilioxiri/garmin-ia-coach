"""Unit tests for coach_tools — handlers + dispatcher."""

from datetime import date, timedelta
from unittest.mock import patch

from tinydb import TinyDB
from tinydb.storages import MemoryStorage

import garmin_coach.coach_tools as ct


def _make_db():
    return TinyDB(storage=MemoryStorage)


def _patch_db(db_instance):
    return patch("garmin_coach.db._db_instance", db_instance)


def _today(offset_days: int = 0) -> str:
    return (date.today() - timedelta(days=offset_days)).isoformat()


def _activity(
    activity_id: str,
    *,
    start: str,
    type_key: str = "running",
    distance_m: float = 5000,
    avg_speed: float = 3.0,
    duration_s: float = 1500,
    avg_hr: float = 150,
):
    return {
        "activityId": activity_id,
        "activityType": {"typeKey": type_key},
        "startTimeLocal": f"{start} 08:00:00",
        "distance": distance_m,
        "averageSpeed": avg_speed,
        "duration": duration_s,
        "averageHR": avg_hr,
    }


# ── find_activity ─────────────────────────────────────────────────────────────


def test_find_activity_filters_by_weekday():
    db_inst = _make_db()
    # 2026-05-01 is friday (viernes) per ISO calendar; verify regardless via date.
    fri = date(2026, 5, 1).isoformat()
    mon = date(2026, 5, 4).isoformat()
    db_inst.table("activities").insert(_activity("1", start=fri))
    db_inst.table("activities").insert(_activity("2", start=mon))
    with _patch_db(db_inst):
        results = ct.find_activity(weekday="viernes", days=90)
    assert len(results) == 1
    assert results[0]["activityId"] == "1"


def test_find_activity_weekday_accepts_unaccented():
    db_inst = _make_db()
    sat = date(2026, 5, 2).isoformat()  # sábado
    db_inst.table("activities").insert(_activity("1", start=sat))
    with _patch_db(db_inst):
        results = ct.find_activity(weekday="sabado", days=90)
    assert len(results) == 1


def test_find_activity_unknown_weekday_returns_empty():
    db_inst = _make_db()
    db_inst.table("activities").insert(_activity("1", start=_today(1)))
    with _patch_db(db_inst):
        assert ct.find_activity(weekday="funday", days=30) == []


def test_find_activity_filters_by_min_distance():
    db_inst = _make_db()
    db_inst.table("activities").insert(
        _activity("short", start=_today(1), distance_m=5000)
    )
    db_inst.table("activities").insert(
        _activity("hm", start=_today(2), distance_m=21100)
    )
    with _patch_db(db_inst):
        results = ct.find_activity(min_distance_km=20, days=90)
    assert [r["activityId"] for r in results] == ["hm"]


def test_find_activity_filters_by_max_distance():
    db_inst = _make_db()
    db_inst.table("activities").insert(
        _activity("short", start=_today(1), distance_m=5000)
    )
    db_inst.table("activities").insert(
        _activity("long", start=_today(2), distance_m=20000)
    )
    with _patch_db(db_inst):
        results = ct.find_activity(max_distance_km=10, days=90)
    assert [r["activityId"] for r in results] == ["short"]


def test_find_activity_filters_by_date_iso():
    db_inst = _make_db()
    target = _today(3)
    db_inst.table("activities").insert(_activity("a", start=target))
    db_inst.table("activities").insert(_activity("b", start=_today(1)))
    with _patch_db(db_inst):
        results = ct.find_activity(date_iso=target, days=30)
    assert [r["activityId"] for r in results] == ["a"]


def test_find_activity_filters_by_type():
    db_inst = _make_db()
    db_inst.table("activities").insert(
        _activity("run", start=_today(1), type_key="running")
    )
    db_inst.table("activities").insert(
        _activity("padel", start=_today(2), type_key="padel", avg_speed=0)
    )
    with _patch_db(db_inst):
        results = ct.find_activity(activity_type="padel", days=30)
    assert [r["activityId"] for r in results] == ["padel"]


def test_find_activity_only_runs_drops_padel():
    db_inst = _make_db()
    db_inst.table("activities").insert(
        _activity("run", start=_today(1), type_key="running")
    )
    db_inst.table("activities").insert(
        _activity("padel", start=_today(2), type_key="padel", avg_speed=0)
    )
    with _patch_db(db_inst):
        results = ct.find_activity(only_runs=True, days=30)
    assert [r["activityId"] for r in results] == ["run"]


def test_find_activity_excludes_outside_window():
    db_inst = _make_db()
    db_inst.table("activities").insert(_activity("recent", start=_today(2)))
    db_inst.table("activities").insert(_activity("old", start=_today(60)))
    with _patch_db(db_inst):
        results = ct.find_activity(days=7)
    assert [r["activityId"] for r in results] == ["recent"]


def test_find_activity_clamps_days_to_max_window():
    db_inst = _make_db()
    db_inst.table("activities").insert(_activity("a", start=_today(1)))
    with _patch_db(db_inst):
        results = ct.find_activity(days=10_000)
    assert len(results) == 1


def test_find_activity_caps_results():
    db_inst = _make_db()
    for i in range(40):
        db_inst.table("activities").insert(_activity(str(i), start=_today(i % 30 + 1)))
    with _patch_db(db_inst):
        results = ct.find_activity(days=90)
    assert len(results) == ct.MAX_ACTIVITIES_RESULT


def test_find_activity_returns_slim_projection():
    db_inst = _make_db()
    db_inst.table("activities").insert(_activity("1", start=_today(1)))
    with _patch_db(db_inst):
        result = ct.find_activity(days=30)[0]
    # slim_activity adds derived fields and replaces duration with duration_hms
    assert "duration" not in result
    assert "duration_hms" in result
    assert "distance_km" in result
    assert "pace_min_per_km" in result


# ── get_recent_activities ─────────────────────────────────────────────────────


def test_get_recent_activities_orders_newest_first():
    db_inst = _make_db()
    db_inst.table("activities").insert(_activity("old", start=_today(5)))
    db_inst.table("activities").insert(_activity("new", start=_today(1)))
    with _patch_db(db_inst):
        results = ct.get_recent_activities(days=30)
    assert [r["activityId"] for r in results] == ["new", "old"]


def test_get_recent_activities_filters_only_runs():
    db_inst = _make_db()
    db_inst.table("activities").insert(
        _activity("run", start=_today(1), type_key="running")
    )
    db_inst.table("activities").insert(
        _activity("padel", start=_today(2), type_key="padel", avg_speed=0)
    )
    with _patch_db(db_inst):
        results = ct.get_recent_activities(days=30, only_runs=True)
    assert [r["activityId"] for r in results] == ["run"]


def test_get_recent_activities_respects_limit():
    db_inst = _make_db()
    for i in range(5):
        db_inst.table("activities").insert(_activity(str(i), start=_today(i + 1)))
    with _patch_db(db_inst):
        results = ct.get_recent_activities(days=30, limit=2)
    assert len(results) == 2


# ── get_activity_detail ───────────────────────────────────────────────────────


def test_get_activity_detail_returns_match():
    db_inst = _make_db()
    db_inst.table("activities").insert(_activity("42", start=_today(1)))
    with _patch_db(db_inst):
        result = ct.get_activity_detail("42")
    assert result["activityId"] == "42"


def test_get_activity_detail_returns_none_when_missing():
    db_inst = _make_db()
    with _patch_db(db_inst):
        assert ct.get_activity_detail("nope") is None


# ── window helpers ────────────────────────────────────────────────────────────


def test_get_sleep_window_filters_by_cutoff_and_slims():
    db_inst = _make_db()
    db_inst.table("sleep").insert({"date": _today(1), "duration_s": 28800, "score": 90})
    db_inst.table("sleep").insert(
        {"date": _today(40), "duration_s": 25200, "score": 70}
    )
    with _patch_db(db_inst):
        results = ct.get_sleep_window(days=7)
    assert len(results) == 1
    assert results[0]["score"] == 90
    assert results[0]["total_h"] == 8.0


def test_get_hrv_window_orders_descending():
    db_inst = _make_db()
    db_inst.table("hrv").insert({"date": _today(2), "lastNight": 50, "weeklyAvg": 48})
    db_inst.table("hrv").insert({"date": _today(1), "lastNight": 55, "weeklyAvg": 49})
    with _patch_db(db_inst):
        results = ct.get_hrv_window(days=7)
    assert [r["date"] for r in results] == [_today(1), _today(2)]


def test_get_body_battery_window_returns_slim_record():
    db_inst = _make_db()
    db_inst.table("body_battery").insert(
        {"date": _today(1), "max": 95, "min": 10, "extra": "x"}
    )
    with _patch_db(db_inst):
        result = ct.get_body_battery_window(days=7)[0]
    assert result == {"date": _today(1), "max": 95, "min": 10}


def test_get_training_readiness_window_slims():
    db_inst = _make_db()
    db_inst.table("training_readiness").insert(
        {
            "date": _today(1),
            "score": 80,
            "level": "high",
            "feedback": "ok",
            "extra": "x",
        }
    )
    with _patch_db(db_inst):
        result = ct.get_training_readiness_window(days=7)[0]
    assert "extra" not in result
    assert result["score"] == 80


# ── get_fitness_snapshot ──────────────────────────────────────────────────────


def test_get_fitness_snapshot_picks_latest():
    db_inst = _make_db()
    db_inst.table("fitness_metrics").insert({"date": "2026-04-01", "vo2max": 50})
    db_inst.table("fitness_metrics").insert({"date": "2026-05-01", "vo2max": 52})
    db_inst.table("race_predictions").insert(
        {
            "date": "2026-05-01",
            "predictions": {
                "time5K": 1200,
                "time10K": 2500,
                "timeHalfMarathon": 5400,
                "timeMarathon": 11000,
            },
        }
    )
    with _patch_db(db_inst):
        snap = ct.get_fitness_snapshot()
    assert snap["fitness_metrics"]["vo2max_running"] == 52
    assert snap["race_predictions"]["time5K"] == 1200
    assert snap["lactate_threshold"] is None
    assert snap["endurance_score"] is None


def test_get_fitness_snapshot_handles_empty_db():
    db_inst = _make_db()
    with _patch_db(db_inst):
        snap = ct.get_fitness_snapshot()
    assert snap == {
        "fitness_metrics": None,
        "race_predictions": None,
        "lactate_threshold": None,
        "endurance_score": None,
    }


# ── search_memory ─────────────────────────────────────────────────────────────


def test_search_memory_substring_match():
    db_inst = _make_db()
    db_inst.table("memory").insert(
        {"note": "Molestia rodilla derecha", "created_at": "2026-04-01"}
    )
    db_inst.table("memory").insert(
        {"note": "Buen rodaje hoy", "created_at": "2026-05-01"}
    )
    with _patch_db(db_inst):
        results = ct.search_memory(query="rodilla")
    assert len(results) == 1
    assert "rodilla" in results[0]["note"].lower()


def test_search_memory_empty_query_returns_all_newest_first():
    db_inst = _make_db()
    db_inst.table("memory").insert({"note": "Nota A", "created_at": "2026-04-01"})
    db_inst.table("memory").insert({"note": "Nota B", "created_at": "2026-05-01"})
    with _patch_db(db_inst):
        results = ct.search_memory()
    assert [r["note"] for r in results] == ["Nota B", "Nota A"]


def test_search_memory_respects_limit():
    db_inst = _make_db()
    for i in range(5):
        db_inst.table("memory").insert(
            {"note": f"n{i}", "created_at": f"2026-05-{i + 1:02d}"}
        )
    with _patch_db(db_inst):
        results = ct.search_memory(limit=2)
    assert len(results) == 2


# ── dispatch_tool_call ────────────────────────────────────────────────────────


def test_dispatch_routes_to_handler():
    db_inst = _make_db()
    db_inst.table("activities").insert(_activity("1", start=_today(1)))
    with _patch_db(db_inst):
        result = ct.dispatch_tool_call("get_recent_activities", {"days": 7})
    assert isinstance(result, list)
    assert result[0]["activityId"] == "1"


def test_dispatch_unknown_tool_returns_error():
    result = ct.dispatch_tool_call("does_not_exist", {})
    assert "error" in result
    assert "unknown tool" in result["error"]


def test_dispatch_bad_args_returns_error():
    # find_activity does not accept `nonsense`
    result = ct.dispatch_tool_call("find_activity", {"nonsense": True})
    assert "error" in result


def test_dispatch_handler_exception_returns_error():
    def boom(**_):
        raise RuntimeError("kaboom")

    with patch.dict(ct.HANDLERS, {"boom": boom}, clear=False):
        result = ct.dispatch_tool_call("boom", {})
    assert "error" in result
    assert "kaboom" in result["error"]


def test_dispatch_handles_none_arguments():
    db_inst = _make_db()
    with _patch_db(db_inst):
        result = ct.dispatch_tool_call("get_fitness_snapshot", None)
    assert isinstance(result, dict)
    assert "fitness_metrics" in result


# ── TOOLS_SPEC ────────────────────────────────────────────────────────────────


def test_tools_spec_covers_all_handlers():
    spec_names = {t["function"]["name"] for t in ct.TOOLS_SPEC}
    assert spec_names == set(ct.HANDLERS.keys())


def test_tools_spec_well_formed():
    for tool in ct.TOOLS_SPEC:
        assert tool["type"] == "function"
        fn = tool["function"]
        assert isinstance(fn["name"], str) and fn["name"]
        assert isinstance(fn["description"], str) and fn["description"]
        assert fn["parameters"]["type"] == "object"
        assert "properties" in fn["parameters"]


# ── get_personal_records ──────────────────────────────────────────────────────


def test_personal_records_finds_best_5k():
    db_inst = _make_db()
    # Two 5K runs: faster wins.
    db_inst.table("activities").insert(
        _activity(
            "slow", start=_today(50), distance_m=5000, duration_s=1500, avg_speed=3.33
        )
    )
    db_inst.table("activities").insert(
        _activity(
            "fast", start=_today(20), distance_m=5050, duration_s=1200, avg_speed=4.21
        )
    )
    with _patch_db(db_inst):
        records = ct.get_personal_records()
    pr_5k = records["records"]["5K"]
    assert pr_5k is not None
    assert pr_5k["activityId"] == "fast"
    assert pr_5k["duration_hms"] == "20:00"


def test_personal_records_half_marathon_tolerance():
    db_inst = _make_db()
    # 21.05 km within ±2% of 21.097 km.
    db_inst.table("activities").insert(
        _activity(
            "hm", start=_today(40), distance_m=21050, duration_s=5400, avg_speed=3.9
        )
    )
    with _patch_db(db_inst):
        records = ct.get_personal_records()
    assert records["records"]["half_marathon"]["activityId"] == "hm"


def test_personal_records_rejects_distance_outside_tolerance():
    db_inst = _make_db()
    # 19 km is too short for a half marathon (±2% of 21.097 ≈ 20.675 - 21.519 km).
    db_inst.table("activities").insert(
        _activity(
            "19k", start=_today(40), distance_m=19000, duration_s=5400, avg_speed=3.5
        )
    )
    with _patch_db(db_inst):
        records = ct.get_personal_records()
    assert records["records"]["half_marathon"] is None


def test_personal_records_ignores_non_runs():
    db_inst = _make_db()
    db_inst.table("activities").insert(
        _activity(
            "cycling_5k",
            start=_today(10),
            type_key="cycling",
            distance_m=5000,
            duration_s=600,
            avg_speed=8.33,
        )
    )
    with _patch_db(db_inst):
        records = ct.get_personal_records()
    assert records["records"]["5K"] is None


def test_personal_records_includes_pace():
    db_inst = _make_db()
    # 5000m / 1500s → 3.33 m/s → 5:00 min/km
    db_inst.table("activities").insert(
        _activity(
            "r", start=_today(10), distance_m=5000, duration_s=1500, avg_speed=3.33
        )
    )
    with _patch_db(db_inst):
        records = ct.get_personal_records()
    assert records["records"]["5K"]["pace_min_per_km"] == "5:00"


def test_personal_records_longest_run():
    db_inst = _make_db()
    db_inst.table("activities").insert(
        _activity(
            "short", start=_today(10), distance_m=5000, duration_s=1500, avg_speed=3.33
        )
    )
    db_inst.table("activities").insert(
        _activity(
            "long", start=_today(20), distance_m=32000, duration_s=10800, avg_speed=2.96
        )
    )
    db_inst.table("activities").insert(
        _activity(
            "long_cycling",
            start=_today(30),
            type_key="cycling",
            distance_m=80000,
            duration_s=10800,
            avg_speed=7.4,
        )
    )
    with _patch_db(db_inst):
        records = ct.get_personal_records()
    longest = records["longest_run"]
    assert longest["activityId"] == "long"
    # Cycling ignored.
    assert longest["distance_km"] == 32.0


def test_personal_records_empty_db():
    db_inst = _make_db()
    with _patch_db(db_inst):
        records = ct.get_personal_records()
    assert records["activities_evaluated"] == 0
    assert records["longest_run"] is None
    assert all(v is None for v in records["records"].values())


def test_personal_records_ignores_activities_with_no_distance_or_duration():
    db_inst = _make_db()
    db_inst.table("activities").insert(
        {
            "activityId": "broken",
            "activityType": {"typeKey": "running"},
            "startTimeLocal": f"{_today(10)} 08:00:00",
            "distance": None,
            "duration": None,
        }
    )
    with _patch_db(db_inst):
        records = ct.get_personal_records()
    assert records["records"]["5K"] is None
    assert records["longest_run"] is None
    assert records["activities_evaluated"] == 1


def test_personal_records_zero_duration_skipped():
    db_inst = _make_db()
    db_inst.table("activities").insert(
        _activity(
            "zero", start=_today(10), distance_m=5000, duration_s=0, avg_speed=3.33
        )
    )
    with _patch_db(db_inst):
        records = ct.get_personal_records()
    assert records["records"]["5K"] is None


def test_personal_records_picks_lowest_duration_on_ties():
    db_inst = _make_db()
    db_inst.table("activities").insert(
        _activity(
            "a", start=_today(10), distance_m=5000, duration_s=1300, avg_speed=3.85
        )
    )
    db_inst.table("activities").insert(
        _activity(
            "b", start=_today(20), distance_m=5000, duration_s=1250, avg_speed=4.0
        )
    )
    db_inst.table("activities").insert(
        _activity(
            "c", start=_today(30), distance_m=5000, duration_s=1500, avg_speed=3.33
        )
    )
    with _patch_db(db_inst):
        records = ct.get_personal_records()
    assert records["records"]["5K"]["activityId"] == "b"


def test_personal_records_listed_in_handlers_and_spec():
    assert "get_personal_records" in ct.HANDLERS
    spec_names = {t["function"]["name"] for t in ct.TOOLS_SPEC}
    assert "get_personal_records" in spec_names
