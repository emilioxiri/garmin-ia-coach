"""Tests for services/tools/registry.py — ToolRegistry."""

from garmin_coach.services.tools.base import Tool, ToolResult
from garmin_coach.services.tools.registry import ToolRegistry, coerce_args_by_schema


class _AddTool(Tool):
    name = "add"
    description = "Add two numbers"
    parameters = {
        "type": "object",
        "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
    }

    def handle(self, a: int = 0, b: int = 0) -> ToolResult:
        return ToolResult(data={"sum": a + b})


class _FailTool(Tool):
    name = "fail"
    description = "Crashes"
    parameters = {"type": "object", "properties": {}}

    def handle(self) -> ToolResult:
        raise RuntimeError("boom")


def test_registry_register_and_specs():
    registry = ToolRegistry()
    registry.register(_AddTool())
    specs = registry.specs()
    assert len(specs) == 1
    assert specs[0]["function"]["name"] == "add"


def test_registry_dispatch_success():
    registry = ToolRegistry()
    registry.register(_AddTool())
    result = registry.dispatch("add", {"a": 3, "b": 4})
    assert result == {"sum": 7}


def test_registry_dispatch_unknown_tool():
    registry = ToolRegistry()
    result = registry.dispatch("no_such_tool", {})
    assert "error" in result
    assert "unknown tool" in result["error"]


def test_registry_dispatch_bad_args():
    registry = ToolRegistry()
    registry.register(_AddTool())
    result = registry.dispatch("add", {"invalid_kwarg": 99})
    assert "error" in result


def test_registry_dispatch_crash():
    registry = ToolRegistry()
    registry.register(_FailTool())
    result = registry.dispatch("fail", {})
    assert "error" in result
    assert "fail" in result["error"]


class _MixedTool(Tool):
    name = "mixed"
    description = "All schema types"
    parameters = {
        "type": "object",
        "properties": {
            "n_int": {"type": "integer"},
            "n_num": {"type": "number"},
            "flag": {"type": "boolean"},
            "label": {"type": "string"},
        },
    }

    def handle(
        self,
        n_int: int = -1,
        n_num: float = -1.0,
        flag: bool = False,
        label: str = "default",
    ) -> ToolResult:
        return ToolResult(
            data={"n_int": n_int, "n_num": n_num, "flag": flag, "label": label}
        )


def test_coerce_drops_none_and_empty_strings():
    schema = {"properties": {"a": {"type": "integer"}, "b": {"type": "string"}}}
    assert coerce_args_by_schema({"a": None, "b": "  "}, schema) == {}


def test_coerce_string_to_integer_and_number():
    schema = {"properties": {"i": {"type": "integer"}, "f": {"type": "number"}}}
    assert coerce_args_by_schema({"i": "7", "f": "21.0975"}, schema) == {
        "i": 7,
        "f": 21.0975,
    }


def test_coerce_string_to_boolean_variants():
    schema = {"properties": {"flag": {"type": "boolean"}}}
    assert coerce_args_by_schema({"flag": "true"}, schema) == {"flag": True}
    assert coerce_args_by_schema({"flag": "FALSE"}, schema) == {"flag": False}
    assert coerce_args_by_schema({"flag": "1"}, schema) == {"flag": True}
    assert coerce_args_by_schema({"flag": "0"}, schema) == {"flag": False}


def test_coerce_drops_unparseable_numeric_strings():
    schema = {"properties": {"n": {"type": "integer"}}}
    assert coerce_args_by_schema({"n": "abc"}, schema) == {}


def test_coerce_passes_through_correct_types():
    schema = {
        "properties": {
            "i": {"type": "integer"},
            "f": {"type": "number"},
            "b": {"type": "boolean"},
            "s": {"type": "string"},
        }
    }
    assert coerce_args_by_schema(
        {"i": 3, "f": 1.5, "b": True, "s": "x"}, schema
    ) == {"i": 3, "f": 1.5, "b": True, "s": "x"}


def test_coerce_unknown_property_passes_through():
    schema = {"properties": {"known": {"type": "integer"}}}
    assert coerce_args_by_schema({"unknown": "anything"}, schema) == {
        "unknown": "anything"
    }


def test_dispatch_coerces_string_args_real_world_payload():
    """Reproduces Groq find_activity payload: all params as strings + empties."""
    registry = ToolRegistry()
    registry.register(_MixedTool())
    payload = {
        "n_int": "",
        "n_num": "21.0975",
        "flag": "true",
        "label": "running",
    }
    result = registry.dispatch("mixed", payload)
    assert result == {
        "n_int": -1,
        "n_num": 21.0975,
        "flag": True,
        "label": "running",
    }


def test_registry_dispatch_strips_none_args_so_defaults_apply():
    """LLM frequently emits `{"a": null, "b": null}`; defaults must survive."""
    registry = ToolRegistry()
    registry.register(_AddTool())
    result = registry.dispatch("add", {"a": None, "b": None})
    assert result == {"sum": 0}


def test_registry_multiple_tools_specs_order():
    registry = ToolRegistry()
    registry.register(_AddTool())
    registry.register(_FailTool())
    names = [s["function"]["name"] for s in registry.specs()]
    assert names == ["add", "fail"]
