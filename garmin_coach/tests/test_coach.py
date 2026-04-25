"""Unit tests for coach.py — CoachSession and generate_daily_briefing."""

import json
import pytest
from unittest.mock import MagicMock, patch


def make_mock_groq_response(content="Respuesta del coach"):
    response = MagicMock()
    response.choices[0].message.content = content
    return response


def make_mock_groq(content="Respuesta del coach"):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = make_mock_groq_response(content)
    return mock_client


EMPTY_CONTEXT = {
    "activities": [],
    "sleep": [],
    "hrv": [],
    "body_battery": [],
    "memory": [],
    "days_covered": 14,
}


# ── CoachSession.chat ─────────────────────────────────────────────────────────

def test_chat_returns_ai_response():
    from garmin_coach.coach import CoachSession

    mock_groq = make_mock_groq("Entrena suave hoy.")
    with (
        patch("garmin_coach.coach.client", mock_groq),
        patch("garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT),
    ):
        session = CoachSession()
        result = session.chat("¿Cómo estoy de forma?")

    assert result == "Entrena suave hoy."


def test_chat_injects_garmin_data_on_first_message():
    from garmin_coach.coach import CoachSession

    mock_groq = make_mock_groq()
    with (
        patch("garmin_coach.coach.client", mock_groq),
        patch("garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT) as mock_ctx,
    ):
        session = CoachSession()
        session.chat("Hola")

    mock_ctx.assert_called_once_with(days=7)
    sent_content = mock_groq.chat.completions.create.call_args[1]["messages"][-1]["content"]
    assert "DATOS GARMIN" in sent_content
    assert "Hola" in sent_content


def test_chat_no_garmin_data_on_subsequent_messages():
    from garmin_coach.coach import CoachSession

    mock_groq = make_mock_groq()
    with (
        patch("garmin_coach.coach.client", mock_groq),
        patch("garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT) as mock_ctx,
    ):
        session = CoachSession()
        session.chat("primer mensaje")
        session.chat("segundo mensaje")

    assert mock_ctx.call_count == 1
    second_call_messages = mock_groq.chat.completions.create.call_args_list[1][1]["messages"]
    last_user_msg = [m for m in second_call_messages if m["role"] == "user"][-1]["content"]
    assert "DATOS GARMIN" not in last_user_msg
    assert "segundo mensaje" == last_user_msg


def test_chat_no_garmin_when_include_false():
    from garmin_coach.coach import CoachSession

    mock_groq = make_mock_groq()
    with (
        patch("garmin_coach.coach.client", mock_groq),
        patch("garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT) as mock_ctx,
    ):
        session = CoachSession()
        session.chat("mensaje sin datos", include_garmin_data=False)

    mock_ctx.assert_not_called()
    sent_content = mock_groq.chat.completions.create.call_args[1]["messages"][-1]["content"]
    assert "DATOS GARMIN" not in sent_content


def test_chat_appends_to_history():
    from garmin_coach.coach import CoachSession

    mock_groq = make_mock_groq("respuesta")
    with (
        patch("garmin_coach.coach.client", mock_groq),
        patch("garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT),
    ):
        session = CoachSession()
        session.chat("hola")

    assert len(session.history) == 2
    assert session.history[0]["role"] == "user"
    assert session.history[1]["role"] == "assistant"
    assert session.history[1]["content"] == "respuesta"


def test_chat_history_trimmed_when_over_40():
    from garmin_coach.coach import CoachSession

    mock_groq = make_mock_groq("ok")
    with (
        patch("garmin_coach.coach.client", mock_groq),
        patch("garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT),
    ):
        session = CoachSession()
        # Pre-fill history to 40 entries (20 exchanges)
        for i in range(20):
            session.history.append({"role": "user", "content": f"msg{i}"})
            session.history.append({"role": "assistant", "content": f"resp{i}"})
        assert len(session.history) == 40

        # One more exchange pushes it to 42, then trimmed to 40
        session.chat("nuevo mensaje")

    assert len(session.history) == 40


def test_chat_error_returns_error_string():
    from garmin_coach.coach import CoachSession

    mock_groq = MagicMock()
    mock_groq.chat.completions.create.side_effect = Exception("conexión fallida")
    with (
        patch("garmin_coach.coach.client", mock_groq),
        patch("garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT),
    ):
        session = CoachSession()
        result = session.chat("hola")

    assert "❌" in result
    assert "conexión fallida" in result


# ── CoachSession.reset ────────────────────────────────────────────────────────

def test_reset_clears_history():
    from garmin_coach.coach import CoachSession

    mock_groq = make_mock_groq()
    with (
        patch("garmin_coach.coach.client", mock_groq),
        patch("garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT),
    ):
        session = CoachSession()
        session.chat("hola")
        assert len(session.history) > 0
        session.reset()

    assert session.history == []


def test_reset_allows_garmin_injection_again():
    from garmin_coach.coach import CoachSession

    mock_groq = make_mock_groq()
    with (
        patch("garmin_coach.coach.client", mock_groq),
        patch("garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT) as mock_ctx,
    ):
        session = CoachSession()
        session.chat("primer mensaje")
        session.reset()
        session.chat("tras reset")

    assert mock_ctx.call_count == 2


# ── generate_daily_briefing ───────────────────────────────────────────────────

def test_briefing_morning_uses_buenos_dias_prompt():
    from garmin_coach.coach import generate_daily_briefing

    mock_groq = make_mock_groq("Briefing de mañana")
    with (
        patch("garmin_coach.coach.client", mock_groq),
        patch("garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT),
    ):
        generate_daily_briefing("morning")

    prompt = mock_groq.chat.completions.create.call_args[1]["messages"][1]["content"]
    assert "Buenos días" in prompt


def test_briefing_evening_uses_buenas_noches_prompt():
    from garmin_coach.coach import generate_daily_briefing

    mock_groq = make_mock_groq("Briefing de noche")
    with (
        patch("garmin_coach.coach.client", mock_groq),
        patch("garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT),
    ):
        generate_daily_briefing("evening")

    prompt = mock_groq.chat.completions.create.call_args[1]["messages"][1]["content"]
    assert "Buenas noches" in prompt


def test_briefing_fetches_7_days_context():
    from garmin_coach.coach import generate_daily_briefing

    mock_groq = make_mock_groq()
    with (
        patch("garmin_coach.coach.client", mock_groq),
        patch("garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT) as mock_ctx,
    ):
        generate_daily_briefing("morning")

    mock_ctx.assert_called_once_with(days=7)


def test_briefing_returns_ai_response():
    from garmin_coach.coach import generate_daily_briefing

    mock_groq = make_mock_groq("Gran día para entrenar.")
    with (
        patch("garmin_coach.coach.client", mock_groq),
        patch("garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT),
    ):
        result = generate_daily_briefing("morning")

    assert result == "Gran día para entrenar."


def test_briefing_error_returns_error_string():
    from garmin_coach.coach import generate_daily_briefing

    mock_groq = MagicMock()
    mock_groq.chat.completions.create.side_effect = Exception("timeout")
    with (
        patch("garmin_coach.coach.client", mock_groq),
        patch("garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT),
    ):
        result = generate_daily_briefing("morning")

    assert "❌" in result
    assert "timeout" in result


def test_briefing_includes_garmin_data_in_prompt():
    from garmin_coach.coach import generate_daily_briefing

    context_with_data = {**EMPTY_CONTEXT, "activities": [{"activityId": "1", "startTimeLocal": "2024-01-01 08:00:00"}]}
    mock_groq = make_mock_groq()
    with (
        patch("garmin_coach.coach.client", mock_groq),
        patch("garmin_coach.coach.get_compact_context_for_ai", return_value=context_with_data),
    ):
        generate_daily_briefing("morning")

    prompt = mock_groq.chat.completions.create.call_args[1]["messages"][1]["content"]
    assert "DATOS" in prompt
    assert "activityId" in prompt
