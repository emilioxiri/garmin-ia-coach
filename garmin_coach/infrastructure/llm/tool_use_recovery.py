"""
infrastructure/llm/tool_use_recovery.py
Pure helpers for recovering from Groq tool_use_failed 400 errors.
"""

from __future__ import annotations

import json
import re

from groq import BadRequestError

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
    return cleaned or None
