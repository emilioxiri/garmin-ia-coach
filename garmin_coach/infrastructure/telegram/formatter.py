"""
infrastructure/telegram/formatter.py
Converts LLM markdown output to Telegram HTML and splits long messages.
"""

from __future__ import annotations

import html
import re
from typing import ClassVar

from garmin_coach.app.logging_setup import get_logger

logger = get_logger(__name__)

_HEADER_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)


class MessageFormatter:
    """Converts LLM responses to Telegram-safe HTML and chunks them."""

    MAX_CHUNK_LEN: ClassVar[int] = 4000

    def to_html(self, text: str) -> str:
        """Convert markdown-like LLM output to Telegram HTML.

        Steps:
          1. Strip leading `#` headers (Telegram HTML has no h1/h2).
          2. HTML-escape `<`, `>`, `&` to avoid breaking the parser.
          3. Convert `**bold**` to `<b>bold</b>`.
        """
        text = _HEADER_RE.sub("", text)
        text = html.escape(text, quote=False)
        text = _BOLD_RE.sub(r"<b>\1</b>", text)
        return text

    def chunk(self, text: str, max_len: int | None = None) -> list[str]:
        """Split text into chunks no longer than max_len, preserving newlines."""
        limit = max_len if max_len is not None else self.MAX_CHUNK_LEN
        if len(text) <= limit:
            return [text]
        parts: list[str] = []
        while text:
            if len(text) <= limit:
                parts.append(text)
                break
            split_at = text.rfind("\n", 0, limit)
            if split_at == -1:
                split_at = limit
            parts.append(text[:split_at])
            text = text[split_at:].lstrip("\n")
        logger.debug("event=chunk_split total_len=%d chunks=%d", len(text), len(parts))
        return parts
