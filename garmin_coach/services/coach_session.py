"""
services/coach_session.py
CoachSession: manages conversation history and the function-calling tool loop.
Depends on LLMClient, ToolRegistry, ContextBuilder, and a system prompt string.
"""

from __future__ import annotations

import json

from groq import BadRequestError

from garmin_coach.app.logging_setup import get_logger
from garmin_coach.infrastructure.llm.message_helpers import (
    coerce_content_to_text,
    normalize_tool_calls,
    serialize_assistant_message,
    trim_history,
)
from garmin_coach.infrastructure.llm.tool_use_recovery import (
    failed_generation_payload,
    parse_bracket_tool_call,
    parse_function_tag,
    parse_inline_tool_calls,
    salvage_tool_use_failed,
)

logger = get_logger(__name__)

MAX_TOOL_ITERATIONS = 5


class CoachSession:
    """Maintains conversation history for a single Telegram user session."""

    def __init__(
        self,
        llm_client,
        tool_registry,
        context_builder,
        system_prompt: str,
        max_iterations: int = MAX_TOOL_ITERATIONS,
        max_history: int = 40,
    ) -> None:
        self._llm = llm_client
        self._registry = tool_registry
        self._context_builder = context_builder
        self._system_prompt = system_prompt
        self._max_iterations = max_iterations
        self._max_history = max_history
        self.history: list[dict] = []

    def chat(self, user_message: str, include_garmin_data: bool = True) -> str:
        """Send a message and return the coach's text response.

        On the first message of a session (empty history) and when
        include_garmin_data=True, injects a compact Garmin context snapshot.
        Runs the tool-calling loop up to max_iterations times.
        """
        if not self.history and include_garmin_data:
            context = self._context_builder.build(days=7)
            enriched = (
                f"[DATOS GARMIN ACTUALIZADOS - últimos 7 días, formato compacto]\n"
                f"{json.dumps(context, ensure_ascii=False)}\n\n"
                f"[MENSAJE DEL ATLETA]\n{user_message}"
            )
        else:
            enriched = user_message

        self.history.append({"role": "user", "content": enriched})

        try:
            assistant_message = ""
            tool_specs = self._registry.specs()
            for iteration in range(self._max_iterations):
                messages = [
                    {"role": "system", "content": self._system_prompt}
                ] + self.history
                logger.info(
                    "event=chat_round iter=%d history_len=%d",
                    iteration,
                    len(self.history),
                )
                try:
                    response = self._llm.chat(messages, tool_specs=tool_specs)
                except BadRequestError as exc:
                    failed = failed_generation_payload(exc)
                    if failed is None:
                        raise
                    parsed = parse_function_tag(failed)
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
                        result = self._registry.dispatch(name, args)
                        try:
                            content = json.dumps(
                                result, ensure_ascii=False, default=str
                            )
                        except (TypeError, ValueError):
                            content = json.dumps({"error": "unserializable result"})
                        self.history.append(
                            {
                                "role": "tool",
                                "tool_call_id": synthetic_id,
                                "name": name,
                                "content": content,
                            }
                        )
                        continue
                    inline = parse_inline_tool_calls(failed)
                    if inline:
                        logger.warning(
                            "Groq tool_use_failed; recovered %d inline JSON tool call(s)",
                            len(inline),
                        )
                        synthetic = self._synthesize_inline_tool_calls(inline)
                        self.history.append(synthetic["assistant_msg"])
                        self.history.extend(synthetic["tool_msgs"])
                        continue
                    bracket = parse_bracket_tool_call(
                        failed, self._registry.known_names()
                    )
                    if bracket:
                        name, args = bracket
                        logger.warning(
                            "Groq tool_use_failed; recovered bracket tool call [%s]",
                            name,
                        )
                        synthetic = self._synthesize_inline_tool_calls([(name, args)])
                        self.history.append(synthetic["assistant_msg"])
                        self.history.extend(synthetic["tool_msgs"])
                        continue
                    salvaged = salvage_tool_use_failed(exc)
                    if salvaged is None:
                        raise
                    logger.warning("Groq tool_use_failed; salvaged plain text fallback")
                    self.history.append({"role": "assistant", "content": salvaged})
                    assistant_message = salvaged
                    break

                self.history.append(serialize_assistant_message(response))
                assistant_message = coerce_content_to_text(
                    getattr(response, "content", "")
                )

                tool_calls = normalize_tool_calls(response)
                logger.info(
                    "event=chat_round_result iter=%d tool_calls=%d",
                    iteration,
                    len(tool_calls),
                )
                if not tool_calls:
                    inline = parse_inline_tool_calls(assistant_message)
                    if inline:
                        logger.warning(
                            "LLM emitted %d inline JSON tool call(s); recovering",
                            len(inline),
                        )
                        synthetic = self._synthesize_inline_tool_calls(inline)
                        self.history[-1] = synthetic["assistant_msg"]
                        self.history.extend(synthetic["tool_msgs"])
                        assistant_message = ""
                        continue
                    bracket = parse_bracket_tool_call(
                        assistant_message, self._registry.known_names()
                    )
                    if bracket:
                        name, args = bracket
                        logger.warning(
                            "LLM emitted [%s] as bracket tool call; recovering", name
                        )
                        synthetic = self._synthesize_inline_tool_calls([(name, args)])
                        self.history[-1] = synthetic["assistant_msg"]
                        self.history.extend(synthetic["tool_msgs"])
                        assistant_message = ""
                        continue
                    break
                self.history.extend(self._execute_tool_calls(tool_calls))
            else:
                logger.warning("MAX_TOOL_ITERATIONS reached without final answer")

            self.history = trim_history(self.history, self._max_history)
            return assistant_message

        except Exception as exc:
            logger.error("Error en LLM: %s", exc)
            return f"❌ Error al conectar con el coach: {exc}"

    def reset(self) -> None:
        self.history = []

    def _synthesize_inline_tool_calls(self, calls: list[tuple[str, dict]]) -> dict:
        """Build a synthetic assistant message + tool result messages from
        tool calls that the model emitted as inline JSON in `content`.
        Replaces the prose-only assistant turn so history stays well-formed.
        """
        base_id = f"inline_{len(self.history)}"
        tool_calls_payload = []
        tool_msgs: list[dict] = []
        for idx, (name, args) in enumerate(calls):
            call_id = f"{base_id}_{idx}"
            tool_calls_payload.append(
                {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(args, ensure_ascii=False),
                    },
                }
            )
            result = self._registry.dispatch(name, args)
            try:
                content = json.dumps(result, ensure_ascii=False, default=str)
            except (TypeError, ValueError):
                content = json.dumps({"error": "unserializable result"})
            tool_msgs.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "name": name,
                    "content": content,
                }
            )
        assistant_msg = {
            "role": "assistant",
            "content": None,
            "tool_calls": tool_calls_payload,
        }
        return {"assistant_msg": assistant_msg, "tool_msgs": tool_msgs}

    def _execute_tool_calls(self, tool_calls: list[dict]) -> list[dict]:
        results: list[dict] = []
        for tc in tool_calls:
            name = tc["name"]
            args = tc["args"] if isinstance(tc.get("args"), dict) else {}
            result = self._registry.dispatch(name, args)
            try:
                content = json.dumps(result, ensure_ascii=False, default=str)
            except (TypeError, ValueError):
                content = json.dumps({"error": "unserializable result"})
            results.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": name,
                    "content": content,
                }
            )
        return results
