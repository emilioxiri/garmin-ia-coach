"""
services/briefing_service.py
BriefingService: generates scheduled morning/evening briefings using the LLM.
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


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
        context = self._context_builder.build(days=7)

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
            return self._llm.briefing(
                [
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": prompt},
                ]
            )
        except Exception as exc:
            logger.error("Error generando briefing: %s", exc)
            return f"❌ No se pudo generar el briefing: {exc}"
