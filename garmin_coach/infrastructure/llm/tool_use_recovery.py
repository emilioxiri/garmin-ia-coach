"""
infrastructure/llm/tool_use_recovery.py
Pure helpers for recovering from Groq tool_use_failed 400 errors.
"""

from __future__ import annotations

import json
import re

from groq import BadRequestError

from garmin_coach.app.logging_setup import get_logger

logger = get_logger(__name__)

BRACKET_TOOL_RE = re.compile(r"\[([A-Za-z_][A-Za-z0-9_]*)\]")

FUNCTION_TAG_RE = re.compile(
    r"<\s*function\s*=.*?(?:</?function>|$)", re.DOTALL | re.IGNORECASE
)
FUNCTION_CALL_RE = re.compile(
    r"<\s*function\s*=\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*"
    r"\(?\s*(?P<args>\{.*?\})\s*\)?\s*"
    r"(?:</?\s*function\s*>|$)",
    re.DOTALL | re.IGNORECASE,
)


def failed_generation_payload(error: BadRequestError) -> str | None:
    """Return the `failed_generation` string from a `tool_use_failed` 400, else None."""
    body = getattr(error, "body", None) or {}
    err = body.get("error") if isinstance(body, dict) else None
    if not isinstance(err, dict) or err.get("code") != "tool_use_failed":
        return None
    failed = err.get("failed_generation")
    if not isinstance(failed, str) or not failed.strip():
        return None
    return failed


def parse_function_tag(text: str) -> tuple[str, dict] | None:
    """Parse a malformed `<function=NAME({...})</function>` tag.

    Returns (name, args_dict) when both are recoverable, else None.
    """
    m = FUNCTION_CALL_RE.search(text)
    if not m:
        return None
    name = m.group("name")
    raw_args = m.group("args")
    try:
        args = json.loads(raw_args)
    except json.JSONDecodeError:
        return None
    if not isinstance(args, dict):
        return None
    return name, args


def salvage_tool_use_failed(error: BadRequestError) -> str | None:
    """Recover plain-text answer from Groq's `tool_use_failed` 400 errors.

    Strips any bogus `<function=...>` tag and returns the remaining prose.
    Returns None when no usable text remains.
    """
    failed = failed_generation_payload(error)
    if failed is None:
        return None
    cleaned = FUNCTION_TAG_RE.sub("", failed).strip()
    if cleaned:
        logger.warning("event=tool_recovery strategy=salvage_plain_text")
    return cleaned or None


def _extract_balanced_json(text: str) -> list[str]:
    """Yield top-level JSON arrays/objects found in `text`, balancing braces.

    Skips brackets/braces inside string literals (incl. escaped quotes).
    """
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in "[{":
            close = "]" if ch == "[" else "}"
            depth = 0
            in_str = False
            esc = False
            j = i
            while j < n:
                c = text[j]
                if in_str:
                    if esc:
                        esc = False
                    elif c == "\\":
                        esc = True
                    elif c == '"':
                        in_str = False
                else:
                    if c == '"':
                        in_str = True
                    elif c == ch:
                        depth += 1
                    elif c == close:
                        depth -= 1
                        if depth == 0:
                            out.append(text[i : j + 1])
                            i = j + 1
                            break
                j += 1
            else:
                break
            continue
        i += 1
    return out


def parse_bracket_tool_call(
    text: str, known_tools: set[str]
) -> tuple[str, dict] | None:
    """Detect `[tool_name]` emitted as plain text for a known tool.

    Returns (tool_name, {}) when matched, else None.
    """
    for m in BRACKET_TOOL_RE.finditer(text):
        name = m.group(1)
        if name in known_tools:
            return name, {}
    return None


def parse_inline_tool_calls(text: str) -> list[tuple[str, dict]] | None:
    """Parse JSON-shaped tool calls emitted as plain text instead of via the
    native tool_calls channel.

    Llama-4 Scout sometimes outputs `[{"name": "find_activity", "parameters":
    {...}}]` (or a single object) inside `content`. We extract every valid
    `{name, args|parameters|arguments}` entry. Returns list of (name, args) or
    None if nothing is recoverable.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    out: list[tuple[str, dict]] = []
    for snippet in _extract_balanced_json(text):
        try:
            parsed = json.loads(snippet)
        except json.JSONDecodeError:
            continue
        items = parsed if isinstance(parsed, list) else [parsed]
        for entry in items:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if not isinstance(name, str):
                continue
            args = (
                entry.get("arguments")
                or entry.get("parameters")
                or entry.get("args")
                or {}
            )
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            if not isinstance(args, dict):
                args = {}
            out.append((name, args))
    return out or None
