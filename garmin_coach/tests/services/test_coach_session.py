"""Tests for services/coach_session.py — CoachSession with DI."""

from unittest.mock import MagicMock

from groq import BadRequestError
from langchain_core.messages import AIMessage

from garmin_coach.services.coach_session import CoachSession

SYSTEM_PROMPT = "Eres un coach."


def _ai(content="Respuesta", tool_calls=None, invalid_tool_calls=None):
    return AIMessage(
        content=content or "",
        tool_calls=tool_calls or [],
        invalid_tool_calls=invalid_tool_calls or [],
    )


def _fake_llm(*responses):
    """LLMClient mock whose chat() iterates through responses."""
    llm = MagicMock()
    llm.chat.side_effect = list(responses)
    return llm


def _fake_registry(dispatch_result=None):
    registry = MagicMock()
    registry.specs.return_value = []
    registry.dispatch.return_value = dispatch_result or {}
    return registry


def _fake_context_builder(context=None):
    cb = MagicMock()
    cb.build.return_value = context or {"activities": [], "days_covered": 7}
    return cb


def _session(llm=None, registry=None, cb=None, prompt=SYSTEM_PROMPT):
    return CoachSession(
        llm_client=llm or _fake_llm(_ai("ok")),
        tool_registry=registry or _fake_registry(),
        context_builder=cb or _fake_context_builder(),
        system_prompt=prompt,
    )


def _make_tool_call(call_id, name, args):
    return {"id": call_id, "name": name, "args": args, "type": "tool_call"}


def _bad_request(body):
    err = BadRequestError.__new__(BadRequestError)
    err.body = body
    err.message = "bad"
    return err


# ── basic chat ────────────────────────────────────────────────────────────────


def test_chat_returns_ai_response():
    session = _session(llm=_fake_llm(_ai("Entrena suave hoy.")))
    assert session.chat("¿Cómo estoy?") == "Entrena suave hoy."


def test_chat_injects_garmin_data_on_first_message():
    cb = _fake_context_builder()
    llm = _fake_llm(_ai("ok"))
    session = _session(llm=llm, cb=cb)
    session.chat("Hola")
    cb.build.assert_called_once_with(days=7)
    sent = llm.chat.call_args[0][0]
    content = sent[-1]["content"]
    assert "DATOS GARMIN" in content
    assert "Hola" in content


def test_chat_no_garmin_data_on_subsequent_messages():
    cb = _fake_context_builder()
    llm = _fake_llm(_ai("first"), _ai("second"))
    session = _session(llm=llm, cb=cb)
    session.chat("primer")
    session.chat("segundo")
    assert cb.build.call_count == 1
    second_call_messages = llm.chat.call_args_list[1][0][0]
    last_user = [m for m in second_call_messages if m["role"] == "user"][-1]["content"]
    assert "DATOS GARMIN" not in last_user
    assert "segundo" == last_user


def test_chat_no_garmin_when_include_false():
    cb = _fake_context_builder()
    llm = _fake_llm(_ai("ok"))
    session = _session(llm=llm, cb=cb)
    session.chat("sin datos", include_garmin_data=False)
    cb.build.assert_not_called()


def test_chat_appends_to_history():
    session = _session(llm=_fake_llm(_ai("respuesta")))
    session.chat("hola")
    assert len(session.history) == 2
    assert session.history[0]["role"] == "user"
    assert session.history[1]["role"] == "assistant"
    assert session.history[1]["content"] == "respuesta"


def test_chat_error_returns_error_string():
    llm = MagicMock()
    llm.chat.side_effect = Exception("timeout")
    llm.specs = MagicMock(return_value=[])
    session = _session(llm=llm)
    result = session.chat("hola")
    assert "❌" in result
    assert "timeout" in result


# ── reset ─────────────────────────────────────────────────────────────────────


def test_reset_clears_history():
    llm = _fake_llm(_ai("ok"), _ai("ok2"))
    session = _session(llm=llm)
    session.chat("hola")
    assert session.history
    session.reset()
    assert session.history == []


def test_reset_allows_garmin_injection_again():
    cb = _fake_context_builder()
    llm = _fake_llm(_ai("first"), _ai("second"))
    session = _session(llm=llm, cb=cb)
    session.chat("primer")
    session.reset()
    session.chat("segundo")
    assert cb.build.call_count == 2


# ── history trimming ──────────────────────────────────────────────────────────


def test_history_trimmed_when_over_limit():
    llm = _fake_llm(_ai("ok"))
    session = _session(llm=llm)
    for i in range(20):
        session.history.append({"role": "user", "content": f"u{i}"})
        session.history.append({"role": "assistant", "content": f"a{i}"})
    assert len(session.history) == 40
    session.chat("nuevo")
    assert len(session.history) <= 40


# ── tool-calling loop ─────────────────────────────────────────────────────────


def test_chat_executes_tool_call_then_returns_final():
    tc = _make_tool_call("c1", "find_activity", {"weekday": "viernes"})
    llm = _fake_llm(
        _ai(content="", tool_calls=[tc]),
        _ai("Tu media maratón fue el viernes."),
    )
    registry = _fake_registry(
        dispatch_result=[{"activityId": "42", "distance_km": 21.1}]
    )
    session = _session(llm=llm, registry=registry)
    result = session.chat("¿Qué hice el viernes?")
    registry.dispatch.assert_called_once_with("find_activity", {"weekday": "viernes"})
    assert result == "Tu media maratón fue el viernes."
    assert llm.chat.call_count == 2


def test_chat_appends_tool_messages_to_history():
    tc = _make_tool_call("c99", "get_fitness_snapshot", {})
    llm = _fake_llm(
        _ai(content="", tool_calls=[tc]),
        _ai("VO2max 52"),
    )
    registry = _fake_registry(
        dispatch_result={"fitness_metrics": {"vo2max_running": 52}}
    )
    session = _session(llm=llm, registry=registry)
    session.chat("VO2max?")
    roles = [m.get("role") for m in session.history]
    assert "tool" in roles
    tool_msg = next(m for m in session.history if m.get("role") == "tool")
    assert tool_msg["tool_call_id"] == "c99"
    assert "vo2max_running" in tool_msg["content"]


def test_chat_stops_after_max_iterations(caplog):
    tc = _make_tool_call("cx", "find_activity", {})
    looping = [_ai(content="", tool_calls=[tc]) for _ in range(5)]
    llm = _fake_llm(*looping)
    registry = _fake_registry(dispatch_result=[])
    session = _session(llm=llm, registry=registry)
    import logging

    with caplog.at_level(logging.WARNING, logger="garmin_coach.services.coach_session"):
        result = session.chat("loop")
    assert result == ""
    assert llm.chat.call_count == 5
    assert any("MAX_TOOL_ITERATIONS" in r.message for r in caplog.records)


def test_chat_serializes_tool_calls_in_history():
    tc = _make_tool_call("c7", "get_sleep_window", {"days": 14})
    llm = _fake_llm(
        _ai(content="", tool_calls=[tc]),
        _ai("Sueño analizado"),
    )
    session = _session(llm=llm)
    session.chat("¿qué tal duermo?")
    assistant_with_tools = next(
        m
        for m in session.history
        if m.get("role") == "assistant" and m.get("tool_calls")
    )
    assert assistant_with_tools["tool_calls"][0]["id"] == "c7"
    assert (
        assistant_with_tools["tool_calls"][0]["function"]["name"] == "get_sleep_window"
    )


# ── tool_use_failed recovery ──────────────────────────────────────────────────


def test_chat_recovers_plain_text_from_tool_use_failed():
    err = _bad_request(
        {
            "error": {
                "code": "tool_use_failed",
                "failed_generation": "El viernes hiciste tu media maratón en 1:39:43.",
            }
        }
    )
    llm = MagicMock()
    llm.chat.side_effect = err
    llm.specs = MagicMock(return_value=[])
    session = _session(llm=llm)
    result = session.chat("¿qué hice el viernes?")
    assert "media maratón" in result


def test_chat_recovers_tool_call_from_function_tag():
    err = _bad_request(
        {
            "error": {
                "code": "tool_use_failed",
                "failed_generation": '<function=find_activity({"weekday": "jueves"})</function>',
            }
        }
    )
    llm = MagicMock()
    llm.chat.side_effect = [err, _ai("El jueves hiciste 8.31 km.")]
    llm.specs = MagicMock(return_value=[])
    registry = _fake_registry(
        dispatch_result=[{"activityId": "9", "distance_km": 8.31}]
    )
    session = _session(llm=llm, registry=registry)
    result = session.chat("¿qué hice el jueves?")
    registry.dispatch.assert_called_once_with("find_activity", {"weekday": "jueves"})
    assert result == "El jueves hiciste 8.31 km."


def test_chat_recovers_inline_json_from_tool_use_failed():
    """Groq sometimes returns 400 with inline JSON tool call in failed_generation."""
    failed = (
        '[{"name": "get_recent_activities", '
        '"parameters": {"activity_type": "running", "days": null}}]'
    )
    err = _bad_request(
        {"error": {"code": "tool_use_failed", "failed_generation": failed}}
    )
    llm = MagicMock()
    llm.chat.side_effect = [err, _ai("Tus últimas carreras: 5K, 8K, 10K.")]
    llm.specs = MagicMock(return_value=[])
    registry = _fake_registry(dispatch_result=[{"activityId": "1"}])
    session = _session(llm=llm, registry=registry)
    result = session.chat("¿últimas carreras?")
    registry.dispatch.assert_called_once_with(
        "get_recent_activities", {"activity_type": "running", "days": None}
    )
    assert result == "Tus últimas carreras: 5K, 8K, 10K."


def test_chat_propagates_non_tool_use_400():
    err = _bad_request({"error": {"code": "context_length_exceeded"}})
    llm = MagicMock()
    llm.chat.side_effect = err
    llm.specs = MagicMock(return_value=[])
    session = _session(llm=llm)
    result = session.chat("hola")
    assert result.startswith("❌")


def test_chat_recovers_inline_json_when_content_is_list_blocks():
    """Newer langchain_groq returns content as `[{type:text,text:...}]`. Recover."""
    inline_blocks = [
        {
            "type": "text",
            "text": '[{"name": "find_activity", "parameters": {"date_iso": "2026-05-05"}}]',
        }
    ]
    llm = _fake_llm(_ai(inline_blocks), _ai("Hecho."))
    registry = _fake_registry(dispatch_result=[{"activityId": "9"}])
    session = _session(llm=llm, registry=registry)

    result = session.chat("¿qué tal?")

    assert result == "Hecho."
    registry.dispatch.assert_called_once_with(
        "find_activity", {"date_iso": "2026-05-05"}
    )


def test_chat_recovers_inline_json_tool_call():
    """LLM emits `[{"name": ..., "parameters": ...}]` as content; we recover."""
    inline_text = (
        '[{"name": "find_activity", "parameters": {"date_iso": "2026-05-05"}}]'
    )
    llm = _fake_llm(_ai(inline_text), _ai("PB sólido. Te veo fino."))
    registry = _fake_registry(dispatch_result=[{"activityId": "9"}])
    session = _session(llm=llm, registry=registry)

    result = session.chat("¿Qué tal mi PB?")

    assert result == "PB sólido. Te veo fino."
    registry.dispatch.assert_called_once_with(
        "find_activity", {"date_iso": "2026-05-05"}
    )
    tool_msg = next(m for m in session.history if m.get("role") == "tool")
    assert tool_msg["name"] == "find_activity"
    assistant_with_tools = next(
        m
        for m in session.history
        if m.get("role") == "assistant" and m.get("tool_calls")
    )
    assert assistant_with_tools["content"] is None
