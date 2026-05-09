"""Tests for services/briefing_service.py — BriefingService."""

from unittest.mock import MagicMock

from garmin_coach.services.briefing_service import BriefingService

SYSTEM_PROMPT = "Eres un coach."


def _make_cb(context=None):
    cb = MagicMock()
    cb.build.return_value = context or {"activities": [], "days_covered": 7}
    return cb


def _make_llm(response="Briefing generado."):
    llm = MagicMock()
    llm.briefing.return_value = response
    return llm


def _make_service(llm=None, cb=None):
    return BriefingService(llm or _make_llm(), cb or _make_cb(), SYSTEM_PROMPT)


def test_generate_morning_returns_llm_response():
    service = _make_service(llm=_make_llm("Buenos días!"))
    result = service.generate("morning")
    assert result == "Buenos días!"


def test_generate_evening_returns_llm_response():
    service = _make_service(llm=_make_llm("Buenas noches!"))
    result = service.generate("evening")
    assert result == "Buenas noches!"


def test_generate_morning_prompt_contains_buenos_dias():
    llm = _make_llm()
    service = _make_service(llm=llm)
    service.generate("morning")
    messages = llm.briefing.call_args[0][0]
    user_content = messages[1]["content"]
    assert "Buenos días" in user_content


def test_generate_evening_prompt_contains_buenas_noches():
    llm = _make_llm()
    service = _make_service(llm=llm)
    service.generate("evening")
    messages = llm.briefing.call_args[0][0]
    user_content = messages[1]["content"]
    assert "Buenas noches" in user_content


def test_generate_fetches_7_days_context():
    cb = _make_cb()
    service = _make_service(cb=cb)
    service.generate("morning")
    cb.build.assert_called_once_with(days=7)


def test_generate_includes_garmin_data_in_prompt():
    context = {"activities": [{"activityId": "1"}], "days_covered": 7}
    llm = _make_llm()
    service = _make_service(llm=llm, cb=_make_cb(context))
    service.generate("morning")
    messages = llm.briefing.call_args[0][0]
    user_content = messages[1]["content"]
    assert "activityId" in user_content


def test_generate_passes_system_prompt():
    llm = _make_llm()
    service = _make_service(llm=llm)
    service.generate("morning")
    messages = llm.briefing.call_args[0][0]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == SYSTEM_PROMPT


def test_generate_error_returns_error_string():
    llm = MagicMock()
    llm.briefing.side_effect = Exception("network error")
    service = _make_service(llm=llm)
    result = service.generate("morning")
    assert "❌" in result
    assert "network error" in result


def test_generate_default_moment_is_morning():
    llm = _make_llm()
    service = _make_service(llm=llm)
    service.generate()
    messages = llm.briefing.call_args[0][0]
    assert "Buenos días" in messages[1]["content"]
