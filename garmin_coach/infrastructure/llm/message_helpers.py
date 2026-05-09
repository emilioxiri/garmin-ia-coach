"""
infrastructure/llm/message_helpers.py
Pure helpers for serializing LangChain messages and managing conversation history.
"""

from __future__ import annotations

import json


def serialize_assistant_message(msg: object) -> dict:
    """Convert a LangChain AIMessage (with possible tool_calls) into a history dict."""
    out: dict = {"role": "assistant", "content": getattr(msg, "content", None) or None}
    tool_calls = getattr(msg, "tool_calls", None) or []
    if tool_calls:
        out["tool_calls"] = [
            {
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["name"],
                    "arguments": json.dumps(tc["args"], ensure_ascii=False),
                },
            }
            for tc in tool_calls
        ]
    return out


def normalize_tool_calls(msg: object) -> list[dict]:
    """Return a flat list of `{id, name, args}` from valid + invalid tool calls.

    LangChain splits well-formed calls into `tool_calls` (parsed args dict) and
    parser failures into `invalid_tool_calls` (raw arg string). Both are coerced
    into the same shape so the executor can treat them uniformly.
    """
    out: list[dict] = []
    for tc in getattr(msg, "tool_calls", None) or []:
        args = tc.get("args") if isinstance(tc.get("args"), dict) else {}
        out.append({"id": tc["id"], "name": tc["name"], "args": args})
    for tc in getattr(msg, "invalid_tool_calls", None) or []:
        raw = tc.get("args")
        if isinstance(raw, dict):
            args = raw
        elif isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                args = parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                args = {}
        else:
            args = {}
        out.append({"id": tc.get("id"), "name": tc.get("name"), "args": args})
    return out


def trim_history(history: list[dict], max_len: int = 40) -> list[dict]:
    """Trim history to last `max_len` entries without orphaning a tool message.

    A `role:tool` entry must follow the assistant message that emitted the
    tool_call; if the trim point lands between them, drop the leading orphan
    tool messages.
    """
    if len(history) <= max_len:
        return history
    trimmed = history[-max_len:]
    while trimmed and trimmed[0].get("role") == "tool":
        trimmed = trimmed[1:]
    return trimmed
