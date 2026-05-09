"""Unit tests for coach.py — CoachSession and generate_daily_briefing."""

from unittest.mock import MagicMock, patch

from groq import BadRequestError
from langchain_core.messages import AIMessage


def make_ai_message(
    content="Respuesta del coach", tool_calls=None, invalid_tool_calls=None
):
    """Build an AIMessage matching LangChain's tool_call shape."""
    return AIMessage(
        content=content or "",
        tool_calls=tool_calls or [],
        invalid_tool_calls=invalid_tool_calls or [],
    )


def make_mock_chat_client(content="Respuesta del coach"):
    """Mock for `chat_client` whose invoke returns a single AIMessage."""
    mock_client = MagicMock()
    mock_client.invoke.return_value = make_ai_message(content)
    return mock_client


def make_mock_briefing_client(content="Respuesta del coach"):
    mock_client = MagicMock()
    mock_client.invoke.return_value = make_ai_message(content)
    return mock_client


def make_tool_call(call_id, name, args):
    """Build a LangChain-style tool_call dict (args already parsed to dict)."""
    return {"id": call_id, "name": name, "args": args, "type": "tool_call"}


def make_chat_with_responses(*responses):
    """Build a mock chat_client whose invoke iterates through `responses`."""
    mock_client = MagicMock()
    mock_client.invoke.side_effect = list(responses)
    return mock_client


def tool_response(*tool_calls, content=None):
    return make_ai_message(content=content or "", tool_calls=list(tool_calls))


def final_response(content="Final"):
    return make_ai_message(content)


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

    mock_client = make_mock_chat_client("Entrena suave hoy.")
    with (
        patch("garmin_coach.coach.chat_client", mock_client),
        patch(
            "garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT
        ),
    ):
        session = CoachSession()
        result = session.chat("¿Cómo estoy de forma?")

    assert result == "Entrena suave hoy."


def test_chat_injects_garmin_data_on_first_message():
    from garmin_coach.coach import CoachSession

    mock_client = make_mock_chat_client()
    with (
        patch("garmin_coach.coach.chat_client", mock_client),
        patch(
            "garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT
        ) as mock_ctx,
    ):
        session = CoachSession()
        session.chat("Hola")

    mock_ctx.assert_called_once_with(days=7)
    sent_messages = mock_client.invoke.call_args[0][0]
    sent_content = sent_messages[-1]["content"]
    assert "DATOS GARMIN" in sent_content
    assert "Hola" in sent_content


def test_chat_no_garmin_data_on_subsequent_messages():
    from garmin_coach.coach import CoachSession

    mock_client = make_mock_chat_client()
    with (
        patch("garmin_coach.coach.chat_client", mock_client),
        patch(
            "garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT
        ) as mock_ctx,
    ):
        session = CoachSession()
        session.chat("primer mensaje")
        session.chat("segundo mensaje")

    assert mock_ctx.call_count == 1
    second_call_messages = mock_client.invoke.call_args_list[1][0][0]
    last_user_msg = [m for m in second_call_messages if m["role"] == "user"][-1][
        "content"
    ]
    assert "DATOS GARMIN" not in last_user_msg
    assert "segundo mensaje" == last_user_msg


def test_chat_no_garmin_when_include_false():
    from garmin_coach.coach import CoachSession

    mock_client = make_mock_chat_client()
    with (
        patch("garmin_coach.coach.chat_client", mock_client),
        patch(
            "garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT
        ) as mock_ctx,
    ):
        session = CoachSession()
        session.chat("mensaje sin datos", include_garmin_data=False)

    mock_ctx.assert_not_called()
    sent_messages = mock_client.invoke.call_args[0][0]
    sent_content = sent_messages[-1]["content"]
    assert "DATOS GARMIN" not in sent_content


def test_chat_appends_to_history():
    from garmin_coach.coach import CoachSession

    mock_client = make_mock_chat_client("respuesta")
    with (
        patch("garmin_coach.coach.chat_client", mock_client),
        patch(
            "garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT
        ),
    ):
        session = CoachSession()
        session.chat("hola")

    assert len(session.history) == 2
    assert session.history[0]["role"] == "user"
    assert session.history[1]["role"] == "assistant"
    assert session.history[1]["content"] == "respuesta"


def test_chat_history_trimmed_when_over_40():
    from garmin_coach.coach import CoachSession

    mock_client = make_mock_chat_client("ok")
    with (
        patch("garmin_coach.coach.chat_client", mock_client),
        patch(
            "garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT
        ),
    ):
        session = CoachSession()
        for i in range(20):
            session.history.append({"role": "user", "content": f"msg{i}"})
            session.history.append({"role": "assistant", "content": f"resp{i}"})
        assert len(session.history) == 40

        session.chat("nuevo mensaje")

    assert len(session.history) == 40


def test_chat_error_returns_error_string():
    from garmin_coach.coach import CoachSession

    mock_client = MagicMock()
    mock_client.invoke.side_effect = Exception("conexión fallida")
    with (
        patch("garmin_coach.coach.chat_client", mock_client),
        patch(
            "garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT
        ),
    ):
        session = CoachSession()
        result = session.chat("hola")

    assert "❌" in result
    assert "conexión fallida" in result


# ── CoachSession.reset ────────────────────────────────────────────────────────


def test_reset_clears_history():
    from garmin_coach.coach import CoachSession

    mock_client = make_mock_chat_client()
    with (
        patch("garmin_coach.coach.chat_client", mock_client),
        patch(
            "garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT
        ),
    ):
        session = CoachSession()
        session.chat("hola")
        assert len(session.history) > 0
        session.reset()

    assert session.history == []


def test_reset_allows_garmin_injection_again():
    from garmin_coach.coach import CoachSession

    mock_client = make_mock_chat_client()
    with (
        patch("garmin_coach.coach.chat_client", mock_client),
        patch(
            "garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT
        ) as mock_ctx,
    ):
        session = CoachSession()
        session.chat("primer mensaje")
        session.reset()
        session.chat("tras reset")

    assert mock_ctx.call_count == 2


# ── generate_daily_briefing ───────────────────────────────────────────────────


def test_briefing_morning_uses_buenos_dias_prompt():
    from garmin_coach.coach import generate_daily_briefing

    mock_client = make_mock_briefing_client("Briefing de mañana")
    with (
        patch("garmin_coach.coach.briefing_client", mock_client),
        patch(
            "garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT
        ),
    ):
        generate_daily_briefing("morning")

    sent_messages = mock_client.invoke.call_args[0][0]
    prompt = sent_messages[1]["content"]
    assert "Buenos días" in prompt


def test_briefing_evening_uses_buenas_noches_prompt():
    from garmin_coach.coach import generate_daily_briefing

    mock_client = make_mock_briefing_client("Briefing de noche")
    with (
        patch("garmin_coach.coach.briefing_client", mock_client),
        patch(
            "garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT
        ),
    ):
        generate_daily_briefing("evening")

    sent_messages = mock_client.invoke.call_args[0][0]
    prompt = sent_messages[1]["content"]
    assert "Buenas noches" in prompt


def test_briefing_fetches_7_days_context():
    from garmin_coach.coach import generate_daily_briefing

    mock_client = make_mock_briefing_client()
    with (
        patch("garmin_coach.coach.briefing_client", mock_client),
        patch(
            "garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT
        ) as mock_ctx,
    ):
        generate_daily_briefing("morning")

    mock_ctx.assert_called_once_with(days=7)


def test_briefing_returns_ai_response():
    from garmin_coach.coach import generate_daily_briefing

    mock_client = make_mock_briefing_client("Gran día para entrenar.")
    with (
        patch("garmin_coach.coach.briefing_client", mock_client),
        patch(
            "garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT
        ),
    ):
        result = generate_daily_briefing("morning")

    assert result == "Gran día para entrenar."


def test_briefing_error_returns_error_string():
    from garmin_coach.coach import generate_daily_briefing

    mock_client = MagicMock()
    mock_client.invoke.side_effect = Exception("timeout")
    with (
        patch("garmin_coach.coach.briefing_client", mock_client),
        patch(
            "garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT
        ),
    ):
        result = generate_daily_briefing("morning")

    assert "❌" in result
    assert "timeout" in result


def test_briefing_includes_garmin_data_in_prompt():
    from garmin_coach.coach import generate_daily_briefing

    context_with_data = {
        **EMPTY_CONTEXT,
        "activities": [{"activityId": "1", "startTimeLocal": "2024-01-01 08:00:00"}],
    }
    mock_client = make_mock_briefing_client()
    with (
        patch("garmin_coach.coach.briefing_client", mock_client),
        patch(
            "garmin_coach.coach.get_compact_context_for_ai",
            return_value=context_with_data,
        ),
    ):
        generate_daily_briefing("morning")

    sent_messages = mock_client.invoke.call_args[0][0]
    prompt = sent_messages[1]["content"]
    assert "DATOS" in prompt
    assert "activityId" in prompt


# ── Tool-call loop ────────────────────────────────────────────────────────────


def test_chat_executes_tool_call_then_returns_final():
    from garmin_coach.coach import CoachSession

    tc = make_tool_call("call_1", "find_activity", {"weekday": "viernes"})
    mock_client = make_chat_with_responses(
        tool_response(tc),
        final_response("Tu media maratón fue el viernes."),
    )

    with (
        patch("garmin_coach.coach.chat_client", mock_client),
        patch(
            "garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT
        ),
        patch(
            "garmin_coach.coach.dispatch_tool_call",
            return_value=[{"activityId": "42", "distance_km": 21.1}],
        ) as mock_dispatch,
    ):
        session = CoachSession()
        result = session.chat("¿Qué hice el viernes?")

    mock_dispatch.assert_called_once_with("find_activity", {"weekday": "viernes"})
    assert result == "Tu media maratón fue el viernes."
    assert mock_client.invoke.call_count == 2


def test_chat_appends_tool_messages_to_history():
    from garmin_coach.coach import CoachSession

    tc = make_tool_call("call_99", "get_fitness_snapshot", {})
    mock_client = make_chat_with_responses(
        tool_response(tc),
        final_response("VO2max 52"),
    )

    with (
        patch("garmin_coach.coach.chat_client", mock_client),
        patch(
            "garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT
        ),
        patch(
            "garmin_coach.coach.dispatch_tool_call",
            return_value={"fitness_metrics": {"vo2max_running": 52}},
        ),
    ):
        session = CoachSession()
        session.chat("VO2max?")

    roles = [m.get("role") for m in session.history]
    assert "tool" in roles
    tool_msg = next(m for m in session.history if m.get("role") == "tool")
    assert tool_msg["tool_call_id"] == "call_99"
    assert tool_msg["name"] == "get_fitness_snapshot"
    assert "vo2max_running" in tool_msg["content"]


def test_chat_handles_invalid_tool_arguments_via_invalid_tool_calls():
    """LangChain routes parser failures to invalid_tool_calls (raw string args)."""
    from garmin_coach.coach import CoachSession

    bad_call = {
        "id": "call_2",
        "name": "find_activity",
        "args": "not json {{{",
        "error": "JSONDecodeError",
        "type": "invalid_tool_call",
    }
    first = make_ai_message(content="", invalid_tool_calls=[bad_call])
    mock_client = make_chat_with_responses(first, final_response("Listo"))

    with (
        patch("garmin_coach.coach.chat_client", mock_client),
        patch(
            "garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT
        ),
        patch(
            "garmin_coach.coach.dispatch_tool_call", return_value=[]
        ) as mock_dispatch,
    ):
        CoachSession().chat("?")

    mock_dispatch.assert_called_once_with("find_activity", {})


def test_chat_stops_after_max_tool_iterations(caplog):
    from garmin_coach.coach import CoachSession, MAX_TOOL_ITERATIONS

    tc = make_tool_call("call_x", "find_activity", {})
    looping_responses = [tool_response(tc) for _ in range(MAX_TOOL_ITERATIONS)]
    mock_client = make_chat_with_responses(*looping_responses)

    with (
        patch("garmin_coach.coach.chat_client", mock_client),
        patch(
            "garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT
        ),
        patch("garmin_coach.coach.dispatch_tool_call", return_value=[]),
        caplog.at_level("WARNING", logger="garmin_coach.coach"),
    ):
        result = CoachSession().chat("loop")

    assert result == ""
    assert mock_client.invoke.call_count == MAX_TOOL_ITERATIONS
    assert any("MAX_TOOL_ITERATIONS" in rec.message for rec in caplog.records)


def test_chat_serializes_assistant_tool_calls_in_history():
    from garmin_coach.coach import CoachSession

    tc = make_tool_call("call_7", "get_sleep_window", {"days": 14})
    mock_client = make_chat_with_responses(
        tool_response(tc),
        final_response("Sueño analizado"),
    )

    with (
        patch("garmin_coach.coach.chat_client", mock_client),
        patch(
            "garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT
        ),
        patch("garmin_coach.coach.dispatch_tool_call", return_value=[{"score": 80}]),
    ):
        session = CoachSession()
        session.chat("¿qué tal duermo?")

    assistant_with_tools = next(
        m
        for m in session.history
        if m.get("role") == "assistant" and m.get("tool_calls")
    )
    assert assistant_with_tools["tool_calls"][0]["id"] == "call_7"
    assert (
        assistant_with_tools["tool_calls"][0]["function"]["name"] == "get_sleep_window"
    )


# ── _trim_history ─────────────────────────────────────────────────────────────


def test_trim_history_drops_orphan_tool_messages():
    from garmin_coach.coach import _trim_history

    hist = [{"role": "user", "content": "old"}] * 5 + [
        {"role": "assistant", "content": None, "tool_calls": [{"id": "x"}]},
        {"role": "tool", "tool_call_id": "x", "name": "y", "content": "{}"},
        {"role": "assistant", "content": "final"},
    ]
    trimmed = _trim_history(hist, max_len=2)
    assert trimmed[0]["role"] != "tool"


def test_trim_history_returns_input_when_under_limit():
    from garmin_coach.coach import _trim_history

    hist = [{"role": "user", "content": "x"}]
    assert _trim_history(hist, max_len=10) is hist


# ── _salvage_tool_use_failed ──────────────────────────────────────────────────


def _make_bad_request(body):
    err = BadRequestError.__new__(BadRequestError)
    err.body = body
    err.message = "bad"
    return err


def test_salvage_strips_function_tag_and_returns_prose():
    from garmin_coach.coach import _salvage_tool_use_failed

    err = _make_bad_request(
        {
            "error": {
                "code": "tool_use_failed",
                "failed_generation": (
                    "El jueves hiciste un rodaje de 8.31 km a 5:41 min/km.\n\n"
                    '<function=find_activity{"weekday": "jueves"}</function>'
                ),
            }
        }
    )
    out = _salvage_tool_use_failed(err)
    assert out is not None
    assert "<function=" not in out
    assert "rodaje de 8.31 km" in out


def test_salvage_returns_none_when_not_tool_use_failed():
    from garmin_coach.coach import _salvage_tool_use_failed

    err = _make_bad_request({"error": {"code": "context_length_exceeded"}})
    assert _salvage_tool_use_failed(err) is None


def test_salvage_returns_none_when_no_failed_generation():
    from garmin_coach.coach import _salvage_tool_use_failed

    err = _make_bad_request({"error": {"code": "tool_use_failed"}})
    assert _salvage_tool_use_failed(err) is None


def test_salvage_returns_none_when_only_function_tag():
    from garmin_coach.coach import _salvage_tool_use_failed

    err = _make_bad_request(
        {
            "error": {
                "code": "tool_use_failed",
                "failed_generation": "<function=find_activity{}</function>",
            }
        }
    )
    assert _salvage_tool_use_failed(err) is None


# ── _parse_function_tag ───────────────────────────────────────────────────────


def test_parse_function_tag_with_parens():
    from garmin_coach.coach import _parse_function_tag

    out = _parse_function_tag(
        '<function=find_activity({"weekday": "jueves"})</function>'
    )
    assert out == ("find_activity", {"weekday": "jueves"})


def test_parse_function_tag_without_parens():
    from garmin_coach.coach import _parse_function_tag

    out = _parse_function_tag('<function=find_activity{"weekday": "jueves"}</function>')
    assert out == ("find_activity", {"weekday": "jueves"})


def test_parse_function_tag_empty_args():
    from garmin_coach.coach import _parse_function_tag

    out = _parse_function_tag("<function=get_fitness_snapshot({})</function>")
    assert out == ("get_fitness_snapshot", {})


def test_parse_function_tag_strips_surrounding_text():
    from garmin_coach.coach import _parse_function_tag

    out = _parse_function_tag(
        'Texto previo <function=find_activity({"a": 1})</function> y posterior'
    )
    assert out == ("find_activity", {"a": 1})


def test_parse_function_tag_returns_none_on_no_match():
    from garmin_coach.coach import _parse_function_tag

    assert _parse_function_tag("Sólo prosa, sin tag") is None


def test_parse_function_tag_returns_none_on_invalid_json():
    from garmin_coach.coach import _parse_function_tag

    assert _parse_function_tag("<function=find_activity({not json})</function>") is None


def test_chat_recovers_from_tool_use_failed_text_only():
    """failed_generation con prosa pura (sin function tag) → salvage textual."""
    from garmin_coach.coach import CoachSession

    err = _make_bad_request(
        {
            "error": {
                "code": "tool_use_failed",
                "failed_generation": "El viernes hiciste tu media maratón en 1:39:43.",
            }
        }
    )
    mock_client = MagicMock()
    mock_client.invoke.side_effect = err
    with (
        patch("garmin_coach.coach.chat_client", mock_client),
        patch(
            "garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT
        ),
    ):
        result = CoachSession().chat("¿qué hice el viernes?")
    assert "media maratón" in result


def test_chat_recovers_tool_call_from_function_tag():
    """failed_generation = `<function=name(args)</function>` → ejecuta tool y continúa."""
    from garmin_coach.coach import CoachSession

    err = _make_bad_request(
        {
            "error": {
                "code": "tool_use_failed",
                "failed_generation": '<function=find_activity({"weekday": "jueves"})</function>',
            }
        }
    )
    mock_client = MagicMock()
    mock_client.invoke.side_effect = [
        err,
        make_ai_message("El jueves hiciste 8.31 km."),
    ]
    with (
        patch("garmin_coach.coach.chat_client", mock_client),
        patch(
            "garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT
        ),
        patch(
            "garmin_coach.coach.dispatch_tool_call",
            return_value=[{"activityId": "9", "distance_km": 8.31}],
        ) as mock_dispatch,
    ):
        session = CoachSession()
        result = session.chat("¿qué hice el jueves?")

    mock_dispatch.assert_called_once_with("find_activity", {"weekday": "jueves"})
    assert result == "El jueves hiciste 8.31 km."
    tool_msg = next(m for m in session.history if m.get("role") == "tool")
    assert tool_msg["name"] == "find_activity"
    assert "8.31" in tool_msg["content"]


def test_chat_recovers_tool_call_no_parens_form():
    from garmin_coach.coach import CoachSession

    err = _make_bad_request(
        {
            "error": {
                "code": "tool_use_failed",
                "failed_generation": "<function=get_fitness_snapshot{}</function>",
            }
        }
    )
    mock_client = MagicMock()
    mock_client.invoke.side_effect = [
        err,
        make_ai_message("VO2max 52"),
    ]
    with (
        patch("garmin_coach.coach.chat_client", mock_client),
        patch(
            "garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT
        ),
        patch(
            "garmin_coach.coach.dispatch_tool_call",
            return_value={"fitness_metrics": {"vo2max_running": 52}},
        ) as mock_dispatch,
    ):
        result = CoachSession().chat("vo2max?")

    mock_dispatch.assert_called_once_with("get_fitness_snapshot", {})
    assert result == "VO2max 52"


def test_chat_propagates_non_tool_use_400():
    from garmin_coach.coach import CoachSession

    err = _make_bad_request({"error": {"code": "context_length_exceeded"}})
    mock_client = MagicMock()
    mock_client.invoke.side_effect = err
    with (
        patch("garmin_coach.coach.chat_client", mock_client),
        patch(
            "garmin_coach.coach.get_compact_context_for_ai", return_value=EMPTY_CONTEXT
        ),
    ):
        result = CoachSession().chat("hola")
    assert result.startswith("❌")
