"""Tests for services/tools/registry.py — ToolRegistry."""

from garmin_coach.services.tools.base import Tool, ToolResult
from garmin_coach.services.tools.registry import ToolRegistry


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
