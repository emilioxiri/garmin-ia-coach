"""Snapshot test: ToolRegistry.specs() must match expected_specs.json.

This guards against accidental schema drift when tool classes are refactored.
The snapshot was captured from the original TOOLS_SPEC in coach_tools.py.
"""

import json
from pathlib import Path

from tinydb import TinyDB
from tinydb.storages import MemoryStorage

from garmin_coach.infrastructure.db.activity_repository import ActivityRepository
from garmin_coach.infrastructure.db.fitness_repository import (
    EnduranceScoreRepository,
    FitnessMetricsRepository,
    LactateThresholdRepository,
    RacePredictionsRepository,
)
from garmin_coach.infrastructure.db.memory_repository import MemoryRepository
from garmin_coach.infrastructure.db.wellness_repository import (
    BodyBatteryRepository,
    HRVRepository,
    SleepRepository,
    TrainingReadinessRepository,
)
from garmin_coach.services.tools.activity_tools import (
    FindActivityTool,
    GetActivityDetailTool,
    GetRecentActivitiesTool,
)
from garmin_coach.services.tools.fitness_tools import (
    GetFitnessSnapshotTool,
    GetPersonalRecordsTool,
)
from garmin_coach.services.tools.memory_tools import SearchMemoryTool
from garmin_coach.services.tools.registry import ToolRegistry
from garmin_coach.services.tools.wellness_tools import (
    GetBodyBatteryWindowTool,
    GetHRVWindowTool,
    GetSleepWindowTool,
    GetTrainingReadinessWindowTool,
)

_SNAPSHOT_PATH = Path(__file__).parent / "expected_specs.json"


def _build_registry() -> ToolRegistry:
    db = TinyDB(storage=MemoryStorage)
    activity_repo = ActivityRepository(db)
    sleep_repo = SleepRepository(db)
    hrv_repo = HRVRepository(db)
    bb_repo = BodyBatteryRepository(db)
    tr_repo = TrainingReadinessRepository(db)
    fm_repo = FitnessMetricsRepository(db)
    rp_repo = RacePredictionsRepository(db)
    lt_repo = LactateThresholdRepository(db)
    es_repo = EnduranceScoreRepository(db)
    mem_repo = MemoryRepository(db)

    registry = ToolRegistry()
    registry.register(FindActivityTool(activity_repo))
    registry.register(GetRecentActivitiesTool(activity_repo))
    registry.register(GetActivityDetailTool(activity_repo))
    registry.register(GetSleepWindowTool(sleep_repo))
    registry.register(GetHRVWindowTool(hrv_repo))
    registry.register(GetBodyBatteryWindowTool(bb_repo))
    registry.register(GetTrainingReadinessWindowTool(tr_repo))
    registry.register(GetFitnessSnapshotTool(fm_repo, rp_repo, lt_repo, es_repo))
    registry.register(GetPersonalRecordsTool(activity_repo))
    registry.register(SearchMemoryTool(mem_repo))
    return registry


def test_specs_match_snapshot():
    expected = json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    registry = _build_registry()
    actual = registry.specs()

    assert len(actual) == len(
        expected
    ), f"Expected {len(expected)} tools, got {len(actual)}"

    expected_by_name = {s["function"]["name"]: s for s in expected}
    actual_by_name = {s["function"]["name"]: s for s in actual}

    assert (
        set(actual_by_name.keys()) == set(expected_by_name.keys())
    ), f"Tool name mismatch.\nExpected: {sorted(expected_by_name)}\nGot: {sorted(actual_by_name)}"

    for name in expected_by_name:
        exp_fn = expected_by_name[name]["function"]
        act_fn = actual_by_name[name]["function"]
        assert act_fn["name"] == exp_fn["name"]
        assert (
            act_fn["description"] == exp_fn["description"]
        ), f"Description mismatch for {name}"
        assert (
            act_fn["parameters"] == exp_fn["parameters"]
        ), f"Parameters mismatch for {name}"
