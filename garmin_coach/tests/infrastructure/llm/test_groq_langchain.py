"""Tests for infrastructure/llm/groq_langchain.py — ChatGroqClient."""

from unittest.mock import MagicMock, patch

from garmin_coach.infrastructure.llm.groq_langchain import ChatGroqClient


def _make_client(model="test-model"):
    with patch(
        "garmin_coach.infrastructure.llm.groq_langchain.ChatGroq"
    ) as MockChatGroq:
        mock_instance = MagicMock()
        MockChatGroq.return_value = mock_instance
        client = ChatGroqClient(model=model)
    return client, mock_instance


def test_construction_creates_two_groq_instances():
    with patch(
        "garmin_coach.infrastructure.llm.groq_langchain.ChatGroq"
    ) as MockChatGroq:
        MockChatGroq.return_value = MagicMock()
        ChatGroqClient(model="my-model", chat_max_tokens=800, briefing_max_tokens=500)
    assert MockChatGroq.call_count == 2


def test_briefing_invokes_client_and_returns_content():
    with patch(
        "garmin_coach.infrastructure.llm.groq_langchain.ChatGroq"
    ) as MockChatGroq:
        mock_chat = MagicMock()
        mock_briefing = MagicMock()
        mock_chat.return_value = "ignored"
        mock_briefing.return_value = "ignored"
        # First call → chat client, second call → briefing client
        MockChatGroq.side_effect = [mock_chat, mock_briefing]
        mock_briefing.invoke.return_value = MagicMock(content="Briefing text")
        client = ChatGroqClient(model="m")

    messages = [{"role": "user", "content": "hello"}]
    result = client.briefing(messages)
    mock_briefing.invoke.assert_called_once_with(messages)
    assert result == "Briefing text"


def test_chat_without_tools_invokes_directly():
    with patch(
        "garmin_coach.infrastructure.llm.groq_langchain.ChatGroq"
    ) as MockChatGroq:
        mock_chat = MagicMock()
        mock_briefing = MagicMock()
        MockChatGroq.side_effect = [mock_chat, mock_briefing]
        fake_response = MagicMock()
        mock_chat.invoke.return_value = fake_response
        client = ChatGroqClient(model="m")

    messages = [{"role": "user", "content": "hello"}]
    result = client.chat(messages, tool_specs=None)
    mock_chat.invoke.assert_called_once_with(messages)
    assert result is fake_response


def test_chat_with_tools_binds_tools_first():
    with patch(
        "garmin_coach.infrastructure.llm.groq_langchain.ChatGroq"
    ) as MockChatGroq:
        mock_chat = MagicMock()
        mock_briefing = MagicMock()
        MockChatGroq.side_effect = [mock_chat, mock_briefing]
        bound_client = MagicMock()
        mock_chat.bind_tools.return_value = bound_client
        fake_response = MagicMock()
        bound_client.invoke.return_value = fake_response
        client = ChatGroqClient(model="m")

    specs = [{"type": "function", "function": {"name": "find_activity"}}]
    messages = [{"role": "user", "content": "hello"}]
    result = client.chat(messages, tool_specs=specs)
    mock_chat.bind_tools.assert_called_once_with(specs)
    bound_client.invoke.assert_called_once_with(messages)
    assert result is fake_response
