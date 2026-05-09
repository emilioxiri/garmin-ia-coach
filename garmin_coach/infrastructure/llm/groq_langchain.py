"""
infrastructure/llm/groq_langchain.py
LangChain ChatGroq implementation of LLMClient.
"""

from __future__ import annotations

from langchain_groq import ChatGroq

from garmin_coach.infrastructure.llm.base import LLMClient


class ChatGroqClient(LLMClient):
    """Wraps two ChatGroq instances — one for tool-calling chat, one for briefings."""

    def __init__(
        self,
        model: str,
        chat_max_tokens: int = 2400,
        briefing_max_tokens: int = 1800,
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
        client = (
            self._chat_client.bind_tools(tool_specs)
            if tool_specs
            else self._chat_client
        )
        return client.invoke(messages)

    def briefing(self, messages: list[dict]) -> str:
        response = self._briefing_client.invoke(messages)
        return response.content
