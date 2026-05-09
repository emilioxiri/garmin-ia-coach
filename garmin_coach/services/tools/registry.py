"""
services/tools/registry.py
ToolRegistry: central registry for function-calling tools.
"""

from __future__ import annotations

import logging
from typing import Any

from garmin_coach.services.tools.base import Tool

logger = logging.getLogger(__name__)


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
            result = tool.handle(**(args or {}))
            if result.error is not None:
                return {"error": result.error}
            return result.data
        except TypeError as e:
            logger.warning("tool %s rejected args %s: %s", name, args, e)
            return {"error": f"bad arguments for {name}: {e}"}
        except Exception as e:
            logger.exception("tool %s crashed", name)
            return {"error": f"{name} failed: {e}"}
