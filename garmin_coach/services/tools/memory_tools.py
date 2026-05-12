"""
services/tools/memory_tools.py
Tool class for searching coach memory notes.
"""

from __future__ import annotations

from typing import Any, ClassVar

from garmin_coach.app.logging_setup import get_logger
from garmin_coach.services.tools.base import Tool, ToolResult

logger = get_logger(__name__)


class SearchMemoryTool(Tool):
    name: ClassVar[str] = "search_memory"
    description: ClassVar[str] = (
        "Busca en las notas que el atleta ha guardado con /memoria (lesiones, sensaciones, decisiones). Substring case-insensitive."
    )
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer"},
        },
    }

    def __init__(self, memory_repo: Any) -> None:
        self._repo = memory_repo

    def handle(self, query: str = "", limit: int = 10) -> ToolResult:
        rows = self._repo.all()
        needle = (query or "").strip().lower()
        if needle:
            rows = [r for r in rows if needle in (r.get("note") or "").lower()]
        rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        cap = max(1, min(int(limit), 50))
        return ToolResult(data=rows[:cap])
