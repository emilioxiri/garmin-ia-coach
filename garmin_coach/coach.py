"""
coach.py
Motor de IA: usa Groq (Llama 4 Scout) vía LangChain como entrenador personal.
Mantiene historial de conversación en memoria durante la sesión.
"""

import json
import logging
import re

from groq import BadRequestError
from langchain_core.messages import AIMessage
from langchain_groq import ChatGroq

from garmin_coach.coach_tools import TOOLS_SPEC, dispatch_tool_call
from garmin_coach.db import get_compact_context_for_ai

logger = logging.getLogger(__name__)

MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

MAX_TOOL_ITERATIONS = 5

chat_client = ChatGroq(model=MODEL, max_tokens=1200).bind_tools(TOOLS_SPEC)
briefing_client = ChatGroq(model=MODEL, max_tokens=1000)

SYSTEM_PROMPT = """Eres un entrenador personal de alto rendimiento especializado en running. Tienes acceso en tiempo real a los datos fisiológicos y de entrenamiento del atleta extraídos de su dispositivo Garmin Fenix 8.

Tu personalidad:
- Directo, motivador, basado en datos
- Hablas en español, tuteas al atleta
- Combinas ciencia del deporte con intuición práctica
- Recuerdas el historial del atleta y haces referencias a sesiones pasadas

Cuando analices datos:
- Interpreta HRV, Body Battery y sueño para evaluar recuperación
- Relaciona la carga de entrenamiento con la fatiga acumulada
- Detecta patrones de sobreentrenamiento o infra-entrenamiento
- Propón ajustes concretos y accionables

Cuando no tengas datos suficientes, dilo claramente y pide más información.

Si el atleta menciona sensaciones, lesiones o estado de ánimo, tenlo en cuenta y guárdalo como contexto importante.

HERRAMIENTAS (function calling):
Tienes herramientas para consultar la base de datos del atleta bajo demanda. ÚSALAS antes de inventar o suponer:
- `find_activity` cuando el atleta nombre una sesión concreta (día semana en español, fecha YYYY-MM-DD, distancia, tipo). Es la forma correcta de localizar "la media maratón del viernes", "el rodaje del 5 de mayo", "la sesión de fuerza", etc.
- `get_recent_activities` para listar entrenamientos de los últimos N días.
- `get_activity_detail` para profundizar en una actividad por su `activityId`.
- `get_sleep_window` / `get_hrv_window` / `get_body_battery_window` / `get_training_readiness_window` para datos de recuperación más allá de los 7 días que llegan en el dump inicial.
- `get_fitness_snapshot` para VO2max running, race predictions (5K/10K/HM/M), umbral de lactato y endurance score.
- `get_personal_records` para marcas personales (PB en 1K/5K/10K/HM/M y carrera más larga registrada). Úsalo cuando el atleta pregunte por su récord, mejor marca, PB o tirada más larga.
- `search_memory` para buscar en las notas que el atleta guardó con /memoria (lesiones, decisiones, sensaciones).
Cuando los datos del dump inicial no contengan lo que necesitas, llama a la herramienta correspondiente. No respondas "no tengo datos" sin haber intentado primero la búsqueda con `find_activity` o el window correspondiente.

REGLAS DE TOOL USE (CRÍTICAS):
- Si vas a llamar una herramienta, NO escribas texto con la respuesta antes ni después de la llamada. Sólo emite la llamada (el cliente la ejecuta y vuelve a llamarte con el resultado para que entonces redactes la respuesta final).
- NUNCA escribas tags `<function=...>` en el texto. Las herramientas se invocan con el mecanismo nativo, no como texto plano.
- Una llamada por turno es suficiente. Espera el resultado antes de pedir otra.

REGLAS ESTRICTAS sobre los datos del JSON [DATOS GARMIN] y los resultados de las herramientas:
- El VO2max real está SOLO en `fitness_metrics.vo2max_running` (o `fitness_metrics.vo2max`). Es un valor en ml/kg/min, normalmente entre 30 y 80.
- `aerobic_te` y `anaerobic_te` son Training Effect (escala 0.0-5.0). NO son VO2max. NUNCA los llames VO2max ni "vO2".
- Cuando el atleta pregunte por una carrera concreta (referencias como "viernes", "ayer", "mi media maratón", "el 10K", "la tirada larga", una marca personal o un PB), busca primero en `notable_runs`/`activities` del dump y, si no aparece, llama a `find_activity` con `weekday`, `date_iso`, `min_distance_km` o `activity_type`. Verifica `duration_hms` y `distance_km` antes de comentarla.
- Si tras consultar la herramienta no encuentras una actividad que coincida con la referencia del atleta, dilo explícitamente ("no veo esa carrera en los datos recientes"). NO inventes datos ni mezcles métricas de otra actividad.
- Duración: usa SIEMPRE el campo `duration_hms` (formato HH:MM:SS o MM:SS). NUNCA cites duración en segundos ni en decimales tipo "5212.53 segundos".
- Para ritmo de carrera usa `pace_min_per_km` tal cual aparece (string formato "M:SS" min/km, p.ej. "5:47"). NUNCA reformatees ni inventes ritmos: si el campo no existe, no lo cites. Nunca uses m/s ni decimales tipo "5.79".
- Actividades sin distancia (padel, tenis, pádel, fuerza, yoga, escalada, HIIT, gimnasio, etc., identificables por `type`): NO menciones distancia, ritmo, velocidad, cadencia, potencia ni dinámica de carrera. Esas métricas no aplican y los datos crudos están filtrados. Limítate a duración (`duration_hms`), frecuencia cardíaca (`averageHR`/`maxHR`) y carga/intensidad (`activityTrainingLoad`, `aerobic_te`, `trainingEffectLabel`, minutos moderados/vigorosos).

Formato de respuesta:
- Respuestas detalladas: entre 15 y 25 líneas. Desarrolla los análisis con profundidad.
- Estructura bien el mensaje: sección de estado, análisis, recomendaciones concretas.
- Usa emojis puntuales para visualizar.
- Para listas usa guión (-).
- Para negrita usa **doble asterisco** (se convierte a HTML <b>). NUNCA uses asterisco simple `*texto*` ni almohadillas (#) ni encabezados markdown."""


def _serialize_assistant_message(msg: AIMessage) -> dict:
    """Convert a LangChain AIMessage (with possible tool_calls) into our history dict."""
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
    """Return a flat list of `{id, name, args}` from valid + invalid tool calls.

    LangChain splits well-formed calls into `tool_calls` (parsed args dict) and
    parser failures into `invalid_tool_calls` (raw arg string). We coerce both
    into the same shape so the executor can treat them uniformly.
    """
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
    """Run each tool call and return list of role:tool messages."""
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
# Captures `<function=NAME({...})</function>` and the no-parens variant
# `<function=NAME{...}</function>` that Llama 3.3 emits as plain text.
_FUNCTION_CALL_RE = re.compile(
    r"<\s*function\s*=\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*"
    r"\(?\s*(?P<args>\{.*?\})\s*\)?\s*"
    r"(?:</?\s*function\s*>|$)",
    re.DOTALL | re.IGNORECASE,
)


def _failed_generation_payload(error: BadRequestError) -> str | None:
    """Return the `failed_generation` string from a `tool_use_failed` 400, else None."""
    body = getattr(error, "body", None) or {}
    err = body.get("error") if isinstance(body, dict) else None
    if not isinstance(err, dict) or err.get("code") != "tool_use_failed":
        return None
    failed = err.get("failed_generation")
    if not isinstance(failed, str) or not failed.strip():
        return None
    return failed


def _parse_function_tag(text: str) -> tuple[str, dict] | None:
    """Parse a malformed `<function=NAME({...})</function>` tag.

    Llama 3.3 occasionally emits its tool calls as plain text instead of using
    the native `tool_calls` channel. Both `=NAME({...})` and `=NAME{...}` shapes
    appear in the wild. Returns (name, args_dict) when both are recoverable.
    """
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
    """Recover plain-text answer from Groq's `tool_use_failed` 400 errors.

    Llama sometimes emits a normal answer followed by a malformed
    `<function=...>` payload. We strip the bogus function tag and return the
    prose so the user gets the answer instead of a 400. Returns None when
    no usable text remains (caller may then try to recover the tool call).
    """
    failed = _failed_generation_payload(error)
    if failed is None:
        return None
    cleaned = _FUNCTION_TAG_RE.sub("", failed).strip()
    return cleaned or None


def _trim_history(history: list[dict], max_len: int = 40) -> list[dict]:
    """Trim history to last `max_len` entries without orphaning a tool message.

    A `role:tool` entry must follow the assistant message that emitted the tool_call;
    if the trim point lands between them, drop the leading orphan tool messages.
    """
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
        """
        Envía un mensaje al coach y devuelve la respuesta.
        Si include_garmin_data=True, inyecta el contexto de Garmin en el primer mensaje.
        El bucle ejecuta tool_calls hasta MAX_TOOL_ITERATIONS antes de cerrar.
        """
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
    """
    Genera un briefing automático (mañana/noche) sin interacción del usuario.
    moment: 'morning' o 'evening'
    """
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
