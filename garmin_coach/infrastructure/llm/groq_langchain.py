"""
infrastructure/llm/groq_langchain.py
LangChain ChatGroq implementation of LLMClient.
"""

from __future__ import annotations

import time

from langchain_groq import ChatGroq

from garmin_coach.app.logging_setup import get_logger
from garmin_coach.infrastructure.llm.base import LLMClient

logger = get_logger(__name__)


class ChatGroqClient(LLMClient):
    """Wraps two ChatGroq instances — one for tool-calling chat, one for briefings."""

    def __init__(
        self,
        model: str,
        chat_max_tokens: int = 2400,
        briefing_max_tokens: int = 2500,
        temperature: float = 0.85,
    ) -> None:
        self._model = model
        self._chat_client = ChatGroq(
            model=model, max_tokens=chat_max_tokens, temperature=temperature
        )
        self._briefing_client = ChatGroq(
            model=model, max_tokens=briefing_max_tokens, temperature=temperature
        )

    def chat(
        self,
        messages: list[dict],
        tool_specs: list[dict] | None = None,
    ) -> object:
        """Invoke the chat client, optionally binding tools.

        Propagates groq.BadRequestError without catching it — recovery lives in
        CoachSession via tool_use_recovery helpers.
        """
        t0 = time.monotonic()
        n_tools = len(tool_specs) if tool_specs else 0
        logger.info(
            "event=llm_call_start model=%s n_tools=%d msgs=%d",
            self._model,
            n_tools,
            len(messages),
        )
        try:
            client = (
                self._chat_client.bind_tools(tool_specs)
                if tool_specs
                else self._chat_client
            )
            response = client.invoke(messages)
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.info(
                "event=llm_call_end model=%s duration_ms=%d", self._model, duration_ms
            )
            return response
        except Exception:
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.error(
                "event=llm_call_failed model=%s duration_ms=%d",
                self._model,
                duration_ms,
                exc_info=True,
            )
            raise

    def briefing(self, messages: list[dict]) -> str:
        t0 = time.monotonic()
        logger.info(
            "event=llm_briefing_start model=%s msgs=%d", self._model, len(messages)
        )
        try:
            response = self._briefing_client.invoke(messages)
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.info(
                "event=llm_briefing_end model=%s duration_ms=%d",
                self._model,
                duration_ms,
            )
            return response.content
        except Exception:
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.error(
                "event=llm_briefing_failed model=%s duration_ms=%d",
                self._model,
                duration_ms,
                exc_info=True,
            )
            raise
