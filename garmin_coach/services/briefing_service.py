"""
services/briefing_service.py
BriefingService: generates scheduled morning/evening briefings using the LLM.
"""

from __future__ import annotations

import json
import time

from garmin_coach.app.logging_setup import get_logger

logger = get_logger(__name__)


class BriefingService:
    """Produces morning/evening briefings via LLMClient + ContextBuilder."""

    def __init__(self, llm_client, context_builder, system_prompt: str) -> None:
        self._llm = llm_client
        self._context_builder = context_builder
        self._system_prompt = system_prompt

    def generate(self, moment: str = "morning") -> str:
        """Generate a scheduled briefing.

        moment: 'morning' or 'evening'.
        Returns the LLM response string, or an error message on failure.
        """
        logger.info("event=briefing_start moment=%s", moment)
        t0 = time.monotonic()
        context = self._context_builder.build(days=7)
        context.pop("race_predictions", None)

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
                "3. Recomendaciones SOLO para mañana — NO para hoy, ya es de noche y no hay tiempo de actuar\n\n"
                f"[DATOS]\n{json.dumps(context, ensure_ascii=False)}"
            )

        try:
            result = self._llm.briefing(
                [
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": prompt},
                ]
            )
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.info(
                "event=briefing_end moment=%s duration_ms=%d", moment, duration_ms
            )
            return result
        except Exception as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.error(
                "event=briefing_failed moment=%s duration_ms=%d",
                moment,
                duration_ms,
                exc_info=True,
            )
            return f"❌ No se pudo generar el briefing: {exc}"
