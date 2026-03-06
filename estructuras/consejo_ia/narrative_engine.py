# -*- coding: utf-8 -*-
"""
Narrative Engine — Claude-powered narrative generation for reports.

Shared utility used by all 4 content generators (macro, RV, RF, asset allocation)
to replace hardcoded narrative text with council-aware, dynamically generated content.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# System prompt enforcing editorial voice — derived from refinador.txt
_SYSTEM_PROMPT = """\
Eres un analista senior de research financiero. Escribes en español profesional, \
directo y conciso. Tu voz es la de un equipo de research — primera persona plural: \
"creemos", "vemos", "nuestra lectura", "esperamos".

REGLAS ESTRICTAS:
- NUNCA uses: "el comité", "el panel", "los especialistas", "el contrarian", \
"el CIO", "AI Council", "agente de riesgo", "tras deliberación", "se identificó", \
"fue cuestionado", "nuestro consejo de inversión".
- NUNCA expongas proceso interno. El cliente lee UN documento escrito por UN equipo.
- Tono DIRECTO y SEGURO. "Vemos riesgo de..." no "Podría existir riesgo de..."
- SECO, no enfático. No uses "extraordinario", "dramáticamente", "inequívoco", \
"transformador", "abrumador". El dato habla por sí mismo.
- CONCISO. Cada frase debe ganarse su lugar.
- Bold (<strong>) solo para: price targets, recomendaciones de acción, cambios \
de posición, y alertas de riesgo crítico.
- Escribe en PROSA, no en listas. Los bullets son solo para datos puntuales.
- La salida es HTML inline (usa <br><br> para párrafos, <strong> para bold). \
NO uses markdown. NO uses encabezados (h1/h2/h3).

FUNDAMENTACION:
- Cada párrafo narrativo debe incluir al menos UN dato concreto (nivel, spread, \
tasa, percentil, variación) que sustente la afirmación. Si no tienes el dato, \
usa el contexto cuantitativo proporcionado.
- MAL: "Mantenemos una postura cautelosa en renta variable global."
- BIEN: "Mantenemos <strong>UW equities</strong>: S&P a 22.1x P/E (percentil 85) \
con earnings revisions cayendo -1.1% — el precio no refleja el deterioro."
- Especifica horizonte temporal: "esperamos X en 3-6 meses", no solo "esperamos X".
- Precisión: spreads en bps, tasas en %, P/E con 1 decimal, probabilidades en rango.

LARGO:
- Target 80-150 palabras por sección salvo que las instrucciones indiquen otro largo.
- Prefiere un párrafo denso a tres párrafos diluidos.
"""


# Module-level correction directive — set by pipeline before regeneration
_active_correction: str = ""


def set_correction_directive(directive: str):
    """Set a correction directive that will be prepended to all narrative calls."""
    global _active_correction
    _active_correction = directive


def clear_correction_directive():
    """Clear the active correction directive."""
    global _active_correction
    _active_correction = ""


def generate_narrative(
    section_name: str,
    prompt: str,
    council_context: str,
    quant_context: str = "",
    company_name: str = "",
    max_tokens: int = 800,
    temperature: float = 0.3,
    correction_directive: str = "",
) -> str:
    """Generate a narrative section using Claude Sonnet.

    Args:
        section_name: Identifier for logging (e.g. "executive_summary").
        prompt: Section-specific instructions for what to generate.
        council_context: Relevant council output text.
        quant_context: Optional quantitative data points as text.
        company_name: Client company name for white-label (empty = "nosotros").
        max_tokens: Max output tokens.
        temperature: Generation temperature.

    Returns:
        Generated HTML narrative string. Empty string on failure.
    """
    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic package not installed — narrative_engine disabled")
        return ""

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set — narrative_engine disabled")
        return ""

    # Build the user message
    identity_line = (
        f'Cuando te refieras a la firma, usa "{company_name}" o "nosotros".'
        if company_name
        else 'Cuando te refieras a la firma, usa "nosotros" o "nuestra lectura".'
    )

    parts = [
        f"## Instrucciones\n{prompt}",
        f"\n## Identidad\n{identity_line}",
    ]
    effective_correction = correction_directive or _active_correction
    if effective_correction:
        parts.append(
            f"\n## CORRECCION OBLIGATORIA (del Refinador)\n"
            f"IMPORTANTE: Debes seguir esta directiva al generar el contenido:\n"
            f"{effective_correction}"
        )
    if council_context:
        parts.append(f"\n## Contexto del council (INSUMO INTERNO — no citar)\n{council_context}")
    if quant_context:
        parts.append(f"\n## Datos cuantitativos\n{quant_context}")

    user_message = "\n".join(parts)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            temperature=temperature,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        text = response.content[0].text.strip()
        logger.info(f"narrative_engine: {section_name} — {len(text)} chars generated")
        return text
    except Exception as e:
        logger.error(f"narrative_engine: {section_name} failed — {e}")
        return ""
