"""
services/tools/base.py
Tool ABC and ToolResult dataclass for the function-calling tool registry.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar


@dataclass
class ToolResult:
    data: Any = None
    error: str | None = None

    def to_dict(self) -> dict:
        if self.error is not None:
            return {"error": self.error}
        return self.data if isinstance(self.data, dict) else {"result": self.data}


class Tool(ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    parameters: ClassVar[dict]

    @abstractmethod
    def handle(self, **kwargs: Any) -> ToolResult: ...

    def to_spec(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
