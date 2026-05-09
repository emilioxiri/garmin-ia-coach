"""Tests for infrastructure/llm/tool_use_recovery.py."""

from groq import BadRequestError

from garmin_coach.infrastructure.llm.tool_use_recovery import (
    failed_generation_payload,
    parse_function_tag,
    salvage_tool_use_failed,
)


def _bad_request(body):
    err = BadRequestError.__new__(BadRequestError)
    err.body = body
    err.message = "bad"
    return err


# ── failed_generation_payload ─────────────────────────────────────────────────


def test_failed_generation_payload_tool_use_failed():
    err = _bad_request(
        {"error": {"code": "tool_use_failed", "failed_generation": "some text"}}
    )
    assert failed_generation_payload(err) == "some text"


def test_failed_generation_payload_wrong_code():
    err = _bad_request({"error": {"code": "context_length_exceeded"}})
    assert failed_generation_payload(err) is None


def test_failed_generation_payload_no_body():
    err = _bad_request(None)
    assert failed_generation_payload(err) is None


def test_failed_generation_payload_missing_failed_generation():
    err = _bad_request({"error": {"code": "tool_use_failed"}})
    assert failed_generation_payload(err) is None


def test_failed_generation_payload_empty_string():
    err = _bad_request(
        {"error": {"code": "tool_use_failed", "failed_generation": "  "}}
    )
    assert failed_generation_payload(err) is None


# ── parse_function_tag ────────────────────────────────────────────────────────


def test_parse_function_tag_with_parens():
    out = parse_function_tag(
        '<function=find_activity({"weekday": "jueves"})</function>'
    )
    assert out == ("find_activity", {"weekday": "jueves"})


def test_parse_function_tag_without_parens():
    out = parse_function_tag('<function=find_activity{"weekday": "jueves"}</function>')
    assert out == ("find_activity", {"weekday": "jueves"})


def test_parse_function_tag_empty_args():
    out = parse_function_tag("<function=get_fitness_snapshot({})</function>")
    assert out == ("get_fitness_snapshot", {})


def test_parse_function_tag_strips_surrounding_text():
    out = parse_function_tag(
        'Texto previo <function=find_activity({"a": 1})</function> y posterior'
    )
    assert out == ("find_activity", {"a": 1})


def test_parse_function_tag_returns_none_on_no_match():
    assert parse_function_tag("Sólo prosa, sin tag") is None


def test_parse_function_tag_returns_none_on_invalid_json():
    assert parse_function_tag("<function=find_activity({not json})</function>") is None


# ── salvage_tool_use_failed ───────────────────────────────────────────────────


def test_salvage_strips_function_tag_returns_prose():
    err = _bad_request(
        {
            "error": {
                "code": "tool_use_failed",
                "failed_generation": (
                    "El jueves hiciste un rodaje de 8.31 km.\n\n"
                    '<function=find_activity{"weekday": "jueves"}</function>'
                ),
            }
        }
    )
    out = salvage_tool_use_failed(err)
    assert out is not None
    assert "<function=" not in out
    assert "rodaje de 8.31 km" in out


def test_salvage_returns_none_when_not_tool_use_failed():
    err = _bad_request({"error": {"code": "context_length_exceeded"}})
    assert salvage_tool_use_failed(err) is None


def test_salvage_returns_none_when_only_function_tag():
    err = _bad_request(
        {
            "error": {
                "code": "tool_use_failed",
                "failed_generation": "<function=find_activity{}</function>",
            }
        }
    )
    assert salvage_tool_use_failed(err) is None


def test_salvage_returns_none_on_missing_generation():
    err = _bad_request({"error": {"code": "tool_use_failed"}})
    assert salvage_tool_use_failed(err) is None
