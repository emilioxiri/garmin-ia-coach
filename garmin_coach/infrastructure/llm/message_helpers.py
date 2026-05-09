"""
infrastructure/llm/message_helpers.py
Pure helpers for serializing LangChain messages and managing conversation history.
"""

from __future__ import annotations

import json


def coerce_content_to_text(content: object) -> str:
    """Flatten LangChain `AIMessage.content` to a plain string.

    Newer langchain_groq versions return content as a list of typed blocks
    (e.g. `[{"type": "text", "text": "..."}]`). Downstream parsers expect
    plain strings, so collapse list/None/other shapes safely.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return str(content)


def serialize_assistant_message(msg: object) -> dict:
    """Convert a LangChain AIMessage (with possible tool_calls) into a history dict."""
    text = coerce_content_to_text(getattr(msg, "content", None))
    out: dict = {"role": "assistant", "content": text or None}
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
