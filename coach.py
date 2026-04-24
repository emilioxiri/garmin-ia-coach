"""
coach.py
Motor de IA: usa Groq (Llama 3.3 70B) como entrenador personal.
Mantiene historial de conversación en memoria durante la sesión.
"""

import json
import logging
from groq import Groq
from db import get_context_for_ai, save_memory

logger = logging.getLogger(__name__)

client = Groq()

MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """Eres un entrenador personal de alto rendimiento especializado en triatlón, running, ciclismo y deportes de resistencia. Tienes acceso en tiempo real a los datos fisiológicos y de entrenamiento del atleta extraídos de su dispositivo Garmin.

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

Formato de respuesta: usa texto claro, con emojis ocasionales para hacer más visual la información. Si tienes que listar datos, usa formato limpio."""


class CoachSession:
    """Mantiene el historial de conversación de una sesión de Telegram."""

    def __init__(self):
        self.history: list[dict] = []

    def chat(self, user_message: str, include_garmin_data: bool = True) -> str:
        """
        Envía un mensaje al coach y devuelve la respuesta.
        Si include_garmin_data=True, inyecta el contexto de Garmin en el primer mensaje.
        """
        if not self.history and include_garmin_data:
            context = get_context_for_ai(days=14)
            enriched_message = (
                f"[DATOS GARMIN ACTUALIZADOS - últimos 14 días]\n"
                f"{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
                f"[MENSAJE DEL ATLETA]\n{user_message}"
            )
        else:
            enriched_message = user_message

        self.history.append({"role": "user", "content": enriched_message})

        try:
            response = client.chat.completions.create(
                model=MODEL,
                max_tokens=1500,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + self.history,
            )
            assistant_message = response.choices[0].message.content
            self.history.append({"role": "assistant", "content": assistant_message})

            if len(self.history) > 40:
                self.history = self.history[-40:]

            return assistant_message

        except Exception as e:
            logger.error(f"Error en Groq API: {e}")
            return f"❌ Error al conectar con el coach: {str(e)}"

    def reset(self):
        self.history = []


def generate_daily_briefing(moment: str = "morning") -> str:
    """
    Genera un briefing automático (mañana/noche) sin interacción del usuario.
    moment: 'morning' o 'evening'
    """
    context = get_context_for_ai(days=7)

    if moment == "morning":
        prompt = (
            "Buenos días. Analiza mis datos de las últimas 24-48h y dame:\n"
            "1. Estado de recuperación (HRV, sueño, Body Battery)\n"
            "2. Recomendación para el entrenamiento de hoy\n"
            "3. Una frase motivadora personalizada basada en mi progreso reciente\n\n"
            f"[DATOS]\n{json.dumps(context, ensure_ascii=False, indent=2)}"
        )
    else:
        prompt = (
            "Buenas noches. Dame el resumen del día:\n"
            "1. Valoración del entrenamiento de hoy (si lo hay)\n"
            "2. Análisis de recuperación para esta noche\n"
            "3. Recomendaciones para mañana\n\n"
            f"[DATOS]\n{json.dumps(context, ensure_ascii=False, indent=2)}"
        )

    try:
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=1000,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error generando briefing: {e}")
        return f"❌ No se pudo generar el briefing: {str(e)}"
