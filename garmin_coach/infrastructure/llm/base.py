"""
infrastructure/llm/base.py
Abstract base class for LLM clients.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        tool_specs: list[dict] | None = None,
    ) -> object:
        """Send messages and return an AIMessage-compatible response."""

    @abstractmethod
    def briefing(self, messages: list[dict]) -> str:
        """Send messages and return the response content string."""
