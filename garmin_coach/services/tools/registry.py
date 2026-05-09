"""
services/tools/registry.py
ToolRegistry: central registry for function-calling tools.
"""

from __future__ import annotations

import logging
from typing import Any

from garmin_coach.services.tools.base import Tool

logger = logging.getLogger(__name__)


_BOOL_TRUE = {"true", "1", "yes", "y", "si", "sí"}
_BOOL_FALSE = {"false", "0", "no", "n"}


def coerce_args_by_schema(args: dict, schema: dict) -> dict:
    """Coerce raw LLM args to the JSON-schema declared types.

    Llama frequently emits all params as strings (`"days": "7"`,
    `"only_runs": "true"`) or as empty strings (`""`) for unset slots.
    This helper:
      - drops None and empty strings (treat as missing → default applies)
      - converts numeric strings to int/float per schema `type`
      - converts "true"/"false" strings to bool
      - leaves already-typed values untouched
      - drops values that fail conversion (default applies)
    """
    props = (schema or {}).get("properties") or {}
    out: dict = {}
    for key, value in (args or {}).items():
        if value is None:
            continue
        prop_type = (props.get(key) or {}).get("type")
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                continue
            if prop_type == "integer":
                try:
                    out[key] = int(float(stripped))
                except ValueError:
                    continue
            elif prop_type == "number":
                try:
                    out[key] = float(stripped)
                except ValueError:
                    continue
            elif prop_type == "boolean":
                low = stripped.lower()
                if low in _BOOL_TRUE:
                    out[key] = True
                elif low in _BOOL_FALSE:
                    out[key] = False
            else:
                out[key] = value
            continue
        if prop_type == "integer" and isinstance(value, float):
            out[key] = int(value)
            continue
        if prop_type == "number" and isinstance(value, int) and not isinstance(value, bool):
            out[key] = float(value)
            continue
        out[key] = value
    return out


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def specs(self) -> list[dict]:
        return [t.to_spec() for t in self._tools.values()]

    def dispatch(self, name: str, args: dict) -> Any:
        """Run a tool by name with kwargs. Returns serializable data or error dict.

        Never raises for missing tool — returns error dict instead.
        """
        tool = self._tools.get(name)
        if tool is None:
            return {"error": f"unknown tool: {name}"}
        try:
            clean_args = coerce_args_by_schema(args or {}, tool.parameters)
            result = tool.handle(**clean_args)
            if result.error is not None:
                return {"error": result.error}
            return result.data
        except TypeError as e:
            logger.warning("tool %s rejected args %s: %s", name, args, e)
            return {"error": f"bad arguments for {name}: {e}"}
        except Exception as e:
            logger.exception("tool %s crashed", name)
            return {"error": f"{name} failed: {e}"}
