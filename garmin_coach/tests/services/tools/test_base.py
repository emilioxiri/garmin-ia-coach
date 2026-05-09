"""Tests for services/tools/base.py — Tool ABC and ToolResult."""

from garmin_coach.services.tools.base import Tool, ToolResult


class _SimpleTool(Tool):
    name = "simple_tool"
    description = "A simple test tool"
    parameters = {"type": "object", "properties": {"x": {"type": "integer"}}}

    def handle(self, x: int = 0) -> ToolResult:
        return ToolResult(data={"value": x * 2})


class _ErrorTool(Tool):
    name = "error_tool"
    description = "Always errors"
    parameters = {"type": "object", "properties": {}}

    def handle(self) -> ToolResult:
        return ToolResult(error="something went wrong")


def test_tool_result_data():
    r = ToolResult(data={"key": "val"})
    assert r.to_dict() == {"key": "val"}


def test_tool_result_list_data():
    r = ToolResult(data=[1, 2, 3])
    assert r.to_dict() == {"result": [1, 2, 3]}


def test_tool_result_error():
    r = ToolResult(error="oops")
    assert r.to_dict() == {"error": "oops"}


def test_tool_to_spec():
    tool = _SimpleTool()
    spec = tool.to_spec()
    assert spec["type"] == "function"
    assert spec["function"]["name"] == "simple_tool"
    assert spec["function"]["description"] == "A simple test tool"
    assert spec["function"]["parameters"] == _SimpleTool.parameters


def test_tool_handle_returns_tool_result():
    tool = _SimpleTool()
    result = tool.handle(x=5)
    assert isinstance(result, ToolResult)
    assert result.data == {"value": 10}


def test_error_tool_result():
    tool = _ErrorTool()
    result = tool.handle()
    assert result.error == "something went wrong"
    assert result.to_dict() == {"error": "something went wrong"}
