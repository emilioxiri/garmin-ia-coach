"""Tests for infrastructure/llm/message_helpers.py."""

import json

from langchain_core.messages import AIMessage

from garmin_coach.infrastructure.llm.message_helpers import (
    coerce_content_to_text,
    normalize_tool_calls,
    serialize_assistant_message,
    trim_history,
)


def test_coerce_content_passes_string():
    assert coerce_content_to_text("hola") == "hola"


def test_coerce_content_handles_none():
    assert coerce_content_to_text(None) == ""


def test_coerce_content_flattens_typed_blocks():
    blocks = [
        {"type": "text", "text": "[{"},
        {"type": "text", "text": '"name": "x"}]'},
    ]
    assert coerce_content_to_text(blocks) == '[{"name": "x"}]'


def test_coerce_content_skips_non_text_blocks():
    blocks = [
        {"type": "text", "text": "hi "},
        {"type": "image", "url": "x"},
        "raw",
    ]
    assert coerce_content_to_text(blocks) == "hi raw"


def test_serialize_assistant_message_flattens_list_content():
    msg = AIMessage(content=[{"type": "text", "text": "foo"}])
    out = serialize_assistant_message(msg)
    assert out["content"] == "foo"


def _ai(content="ok", tool_calls=None, invalid_tool_calls=None):
    return AIMessage(
        content=content or "",
        tool_calls=tool_calls or [],
        invalid_tool_calls=invalid_tool_calls or [],
    )


def _tc(call_id, name, args):
    return {"id": call_id, "name": name, "args": args, "type": "tool_call"}


# ── serialize_assistant_message ───────────────────────────────────────────────


def test_serialize_plain_message():
    msg = _ai("Hello!")
    out = serialize_assistant_message(msg)
    assert out["role"] == "assistant"
    assert out["content"] == "Hello!"
    assert "tool_calls" not in out


def test_serialize_empty_content_becomes_none():
    msg = _ai("")
    out = serialize_assistant_message(msg)
    assert out["content"] is None


def test_serialize_with_tool_calls():
    tc = _tc("id1", "find_activity", {"weekday": "viernes"})
    msg = _ai("", tool_calls=[tc])
    out = serialize_assistant_message(msg)
    assert "tool_calls" in out
    assert out["tool_calls"][0]["id"] == "id1"
    assert out["tool_calls"][0]["function"]["name"] == "find_activity"
    args = json.loads(out["tool_calls"][0]["function"]["arguments"])
    assert args == {"weekday": "viernes"}


# ── normalize_tool_calls ──────────────────────────────────────────────────────


def test_normalize_valid_tool_calls():
    tc = _tc("id1", "get_sleep_window", {"days": 7})
    msg = _ai("", tool_calls=[tc])
    result = normalize_tool_calls(msg)
    assert len(result) == 1
    assert result[0] == {"id": "id1", "name": "get_sleep_window", "args": {"days": 7}}


def test_normalize_invalid_tool_calls_with_valid_json():
    bad = {
        "id": "id2",
        "name": "find_activity",
        "args": '{"weekday": "lunes"}',
        "type": "invalid_tool_call",
    }
    msg = _ai("", invalid_tool_calls=[bad])
    result = normalize_tool_calls(msg)
    assert len(result) == 1
    assert result[0]["args"] == {"weekday": "lunes"}


def test_normalize_invalid_tool_calls_with_bad_json():
    bad = {
        "id": "id3",
        "name": "find_activity",
        "args": "not json",
        "type": "invalid_tool_call",
    }
    msg = _ai("", invalid_tool_calls=[bad])
    result = normalize_tool_calls(msg)
    assert result[0]["args"] == {}


def test_normalize_empty_message():
    msg = _ai("no tools")
    assert normalize_tool_calls(msg) == []


def test_normalize_combines_valid_and_invalid():
    tc = _tc("v1", "get_hrv_window", {"days": 3})
    bad = {
        "id": "b1",
        "name": "search_memory",
        "args": '{"query": "lesión"}',
        "type": "invalid_tool_call",
    }
    msg = _ai("", tool_calls=[tc], invalid_tool_calls=[bad])
    result = normalize_tool_calls(msg)
    assert len(result) == 2


# ── trim_history ──────────────────────────────────────────────────────────────


def test_trim_history_no_trim_needed():
    hist = [{"role": "user", "content": "x"}]
    result = trim_history(hist, max_len=10)
    assert result is hist


def test_trim_history_basic_trim():
    hist = [{"role": "user", "content": f"msg{i}"} for i in range(50)]
    result = trim_history(hist, max_len=40)
    assert len(result) == 40


def test_trim_history_drops_orphan_tool_messages():
    hist = [{"role": "user", "content": "old"}] * 5 + [
        {"role": "assistant", "content": None, "tool_calls": [{"id": "x"}]},
        {"role": "tool", "tool_call_id": "x", "name": "y", "content": "{}"},
        {"role": "assistant", "content": "final"},
    ]
    trimmed = trim_history(hist, max_len=2)
    assert trimmed[0]["role"] != "tool"


def test_trim_history_preserves_non_orphan_tool():
    hist = [
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": None, "tool_calls": [{"id": "t1"}]},
        {"role": "tool", "tool_call_id": "t1", "name": "f", "content": "{}"},
        {"role": "assistant", "content": "final"},
    ]
    result = trim_history(hist, max_len=4)
    assert len(result) == 4
