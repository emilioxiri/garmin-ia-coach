"""
coach.py — backward-compatibility shim (Phase 3 refactor).

bot.py imports `CoachSession` and `generate_daily_briefing` from here.
This shim delegates to the new service layer via a lazy Container singleton.

TEMPORAL — Phase 5 eliminates this when bot.py is rewritten as OOP handlers.

The old module-level globals (chat_client, briefing_client, SYSTEM_PROMPT,
dispatch_tool_call, _trim_history, _parse_function_tag, _salvage_tool_use_failed,
MAX_TOOL_ITERATIONS) are preserved so that test_coach.py keeps working until
the legacy tests are deleted in Phase 3 cleanup.
"""

from __future__ import annotations

import json
import logging
import re

from groq import BadRequestError
from langchain_core.messages import AIMessage
from langchain_groq import ChatGroq

from garmin_coach.coach_tools import TOOLS_SPEC, dispatch_tool_call
from garmin_coach.db import get_compact_context_for_ai
from garmin_coach.prompts import read_system_prompt

logger = logging.getLogger(__name__)

MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

MAX_TOOL_ITERATIONS = 5

chat_client = ChatGroq(model=MODEL, max_tokens=1200).bind_tools(TOOLS_SPEC)
briefing_client = ChatGroq(model=MODEL, max_tokens=1000)

SYSTEM_PROMPT = read_system_prompt()


def _serialize_assistant_message(msg: AIMessage) -> dict:
    out: dict = {"role": "assistant", "content": msg.content or None}
    tool_calls = getattr(msg, "tool_calls", None) or []
    if tool_calls:
        out["tool_calls"] = [
            {
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["name"],
                    "arguments": json.dumps(tc["args"], ensure_ascii=False),
                },
            }
            for tc in tool_calls
        ]
    return out


def _normalize_tool_calls(msg: AIMessage) -> list[dict]:
    out: list[dict] = []
    for tc in getattr(msg, "tool_calls", None) or []:
        args = tc.get("args") if isinstance(tc.get("args"), dict) else {}
        out.append({"id": tc["id"], "name": tc["name"], "args": args})
    for tc in getattr(msg, "invalid_tool_calls", None) or []:
        raw = tc.get("args")
        if isinstance(raw, dict):
            args = raw
        elif isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                args = parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                args = {}
        else:
            args = {}
        out.append({"id": tc.get("id"), "name": tc.get("name"), "args": args})
    return out


def _execute_tool_calls(tool_calls: list[dict]) -> list[dict]:
    results: list[dict] = []
    for tc in tool_calls:
        name = tc["name"]
        args = tc["args"] if isinstance(tc.get("args"), dict) else {}
        result = dispatch_tool_call(name, args)
        try:
            content = json.dumps(result, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            content = json.dumps({"error": "unserializable result"}, ensure_ascii=False)
        results.append(
            {
                "role": "tool",
                "tool_call_id": tc["id"],
                "name": name,
                "content": content,
            }
        )
    return results


_FUNCTION_TAG_RE = re.compile(
    r"<\s*function\s*=.*?(?:</?function>|$)", re.DOTALL | re.IGNORECASE
)
_FUNCTION_CALL_RE = re.compile(
    r"<\s*function\s*=\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*"
    r"\(?\s*(?P<args>\{.*?\})\s*\)?\s*"
    r"(?:</?\s*function\s*>|$)",
    re.DOTALL | re.IGNORECASE,
)


def _failed_generation_payload(error: BadRequestError) -> str | None:
    body = getattr(error, "body", None) or {}
    err = body.get("error") if isinstance(body, dict) else None
    if not isinstance(err, dict) or err.get("code") != "tool_use_failed":
        return None
    failed = err.get("failed_generation")
    if not isinstance(failed, str) or not failed.strip():
        return None
    return failed


def _parse_function_tag(text: str) -> tuple[str, dict] | None:
    m = _FUNCTION_CALL_RE.search(text)
    if not m:
        return None
    name = m.group("name")
    raw_args = m.group("args")
    try:
        args = json.loads(raw_args)
    except json.JSONDecodeError:
        return None
    if not isinstance(args, dict):
        return None
    return name, args


def _salvage_tool_use_failed(error: BadRequestError) -> str | None:
    failed = _failed_generation_payload(error)
    if failed is None:
        return None
    cleaned = _FUNCTION_TAG_RE.sub("", failed).strip()
    return cleaned or None


def _trim_history(history: list[dict], max_len: int = 40) -> list[dict]:
    if len(history) <= max_len:
        return history
    trimmed = history[-max_len:]
    while trimmed and trimmed[0].get("role") == "tool":
        trimmed = trimmed[1:]
    return trimmed


class CoachSession:
    """Mantiene el historial de conversación de una sesión de Telegram."""

    def __init__(self):
        self.history: list[dict] = []

    def chat(self, user_message: str, include_garmin_data: bool = True) -> str:
        if not self.history and include_garmin_data:
            context = get_compact_context_for_ai(days=7)
            enriched_message = (
                f"[DATOS GARMIN ACTUALIZADOS - últimos 7 días, formato compacto]\n"
                f"{json.dumps(context, ensure_ascii=False)}\n\n"
                f"[MENSAJE DEL ATLETA]\n{user_message}"
            )
        else:
            enriched_message = user_message

        self.history.append({"role": "user", "content": enriched_message})

        try:
            assistant_message = ""
            for _ in range(MAX_TOOL_ITERATIONS):
                try:
                    messages = [
                        {"role": "system", "content": SYSTEM_PROMPT}
                    ] + self.history
                    response = chat_client.invoke(messages)
                except BadRequestError as e:
                    failed = _failed_generation_payload(e)
                    if failed is None:
                        raise
                    parsed = _parse_function_tag(failed)
                    if parsed is not None:
                        name, args = parsed
                        logger.warning(
                            "Groq tool_use_failed; recovered tool call %s(%s)",
                            name,
                            args,
                        )
                        synthetic_id = f"salvaged_{len(self.history)}"
                        self.history.append(
                            {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": synthetic_id,
                                        "type": "function",
                                        "function": {
                                            "name": name,
                                            "arguments": json.dumps(args),
                                        },
                                    }
                                ],
                            }
                        )
                        result = dispatch_tool_call(name, args)
                        try:
                            content = json.dumps(
                                result, ensure_ascii=False, default=str
                            )
                        except (TypeError, ValueError):
                            content = json.dumps(
                                {"error": "unserializable result"}, ensure_ascii=False
                            )
                        self.history.append(
                            {
                                "role": "tool",
                                "tool_call_id": synthetic_id,
                                "name": name,
                                "content": content,
                            }
                        )
                        continue
                    salvaged = _salvage_tool_use_failed(e)
                    if salvaged is None:
                        raise
                    logger.warning("Groq tool_use_failed; salvaged plain text fallback")
                    self.history.append({"role": "assistant", "content": salvaged})
                    assistant_message = salvaged
                    break

                self.history.append(_serialize_assistant_message(response))
                assistant_message = response.content or ""

                tool_calls = _normalize_tool_calls(response)
                if not tool_calls:
                    break
                self.history.extend(_execute_tool_calls(tool_calls))
            else:
                logger.warning("MAX_TOOL_ITERATIONS reached without final answer")

            self.history = _trim_history(self.history)
            return assistant_message

        except Exception as e:
            logger.error(f"Error en LLM: {e}")
            return f"❌ Error al conectar con el coach: {str(e)}"

    def reset(self):
        self.history = []


def generate_daily_briefing(moment: str = "morning") -> str:
    context = get_compact_context_for_ai(days=7)

    if moment == "morning":
        prompt = (
            "Buenos días. Analiza mis datos de las últimas 24-48h y dame:\n"
            "1. Estado de recuperación (HRV, sueño, Body Battery)\n"
            "2. Recomendación para el entrenamiento de hoy\n"
            "3. Una frase motivadora personalizada basada en mi progreso reciente\n\n"
            f"[DATOS]\n{json.dumps(context, ensure_ascii=False)}"
        )
    else:
        prompt = (
            "Buenas noches. Dame el resumen del día:\n"
            "1. Valoración del entrenamiento de hoy (si lo hay)\n"
            "2. Análisis de recuperación para esta noche\n"
            "3. Recomendaciones para mañana\n\n"
            f"[DATOS]\n{json.dumps(context, ensure_ascii=False)}"
        )

    try:
        response = briefing_client.invoke(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
        )
        return response.content
    except Exception as e:
        logger.error(f"Error generando briefing: {e}")
        return f"❌ No se pudo generar el briefing: {str(e)}"
