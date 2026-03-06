# -*- coding: utf-8 -*-
"""
Report Coherence Auditor
========================

Post-generation QA step (Phase 4.5) that verifies coherence
within and across the 4 investment reports.

Single Sonnet call: ~$0.02-0.03 per run.
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def _extract_audit_payload(contents: Dict[str, Dict]) -> str:
    """Extract key stance, positioning, and data points from the 4 content dicts."""

    lines: List[str] = []

    # --- MACRO ---
    macro = contents.get('macro', {})
    if macro:
        me = macro.get('resumen_ejecutivo', {})
        mc = macro.get('conclusiones', {})
        lines.append("## MACRO REPORT")
        postura = me.get('postura', {})
        lines.append(f"View: {postura.get('view', 'N/D')}")
        # Key takeaways (first 3)
        kts = me.get('key_takeaways', [])
        if kts:
            lines.append(f"Takeaways: {'; '.join(str(k)[:120] for k in kts[:3])}")
        # Conclusions - vistas
        vistas = mc.get('vistas', [])
        for v in vistas[:4]:
            if isinstance(v, dict):
                lines.append(f"  Vista: {v.get('tema','')} → {v.get('vista_grb','')} (vs consenso: {v.get('vs_consenso','')})")
        pos_res = mc.get('posicionamiento_resumen', '')
        if pos_res:
            lines.append(f"Positioning: {str(pos_res)[:200]}")
        # Forecasts
        ft = me.get('forecasts_table', [])
        if isinstance(ft, list):
            for f in ft[:6]:
                if isinstance(f, dict):
                    lines.append(f"  Forecast: {f.get('variable','')} = {f.get('valor','')}")
        elif isinstance(ft, dict):
            for k, v in list(ft.items())[:6]:
                lines.append(f"  Forecast: {k} = {v}")

    # --- RV ---
    rv = contents.get('rv', {})
    if rv:
        lines.append("\n## RENTA VARIABLE REPORT")
        pg = rv.get('resumen_ejecutivo', {}).get('postura_global', {})
        lines.append(f"View: {pg.get('view', 'N/D')} | Cambio: {pg.get('cambio', 'N/D')} | Conviccion: {pg.get('conviccion', 'N/D')}")
        lines.append(f"Driver: {pg.get('driver_principal', 'N/D')}")
        lines.append(f"Narrativa: {str(pg.get('narrativa', ''))[:200]}")
        # Key calls
        kc = rv.get('resumen_ejecutivo', {}).get('key_calls', [])
        if kc:
            lines.append(f"Key calls: {'; '.join(str(k)[:100] for k in kc[:4])}")
        # Positioning table
        rp = rv.get('resumen_posicionamiento', {})
        for row in rp.get('tabla_final', [])[:6]:
            if isinstance(row, dict):
                lines.append(f"  {row.get('categoria', '')}: {row.get('recomendacion', '')}")
        mk = rp.get('mensaje_clave', '')
        if mk:
            lines.append(f"Mensaje clave: {str(mk)[:200]}")
        # Risks
        risks = rv.get('riesgos_catalizadores', {})
        if isinstance(risks, dict):
            for r in risks.get('riesgos', [])[:3]:
                if isinstance(r, dict):
                    lines.append(f"  Riesgo: {r.get('riesgo', '')} (prob: {r.get('probabilidad', '')}, imp: {r.get('impacto', '')})")

    # --- RF ---
    rf = contents.get('rf', {})
    if rf:
        lines.append("\n## RENTA FIJA REPORT")
        pg = rf.get('resumen_ejecutivo', {}).get('postura_global', {})
        lines.append(f"View: {pg.get('view', 'N/D')} | Cambio: {pg.get('cambio', 'N/D')} | Conviccion: {pg.get('conviccion', 'N/D')}")
        lines.append(f"Driver: {pg.get('driver_principal', 'N/D')}")
        lines.append(f"Narrativa: {str(pg.get('narrativa', ''))[:200]}")
        # Rates environment
        at = rf.get('ambiente_tasas', {})
        if isinstance(at, dict):
            lines.append(f"Rates narrative: {str(at.get('narrativa', ''))[:200]}")
            tabla = at.get('tabla_tasas', [])
            for row in tabla[:4]:
                if isinstance(row, dict):
                    lines.append(f"  {row.get('tasa', '')}: {row.get('actual', '')} → {row.get('esperado_12m', '')}")
        # Positioning table
        rp = rf.get('resumen_posicionamiento', {})
        for row in rp.get('tabla_final', [])[:6]:
            if isinstance(row, dict):
                lines.append(f"  {row.get('dimension', '')}: {row.get('recomendacion', '')}")
        mk = rp.get('mensaje_clave', '')
        if mk:
            lines.append(f"Mensaje clave: {str(mk)[:200]}")
        # Chile rates
        chile = rf.get('chile', {})
        if isinstance(chile, dict):
            lines.append(f"Chile TPM: {chile.get('tpm_actual', 'N/D')}")

    # --- ASSET ALLOCATION ---
    aa = contents.get('aa', {})
    if aa:
        lines.append("\n## ASSET ALLOCATION REPORT")
        ae = aa.get('resumen_ejecutivo', {})
        postura = ae.get('postura', {})
        lines.append(f"View: {postura.get('view', 'N/D')} | Sesgo: {postura.get('sesgo', 'N/D')} | Conviccion: {postura.get('conviccion', 'N/D')}")
        lines.append(f"Catalizador: {ae.get('catalizador', 'N/D')}")
        # Key points
        kp = ae.get('key_points', [])
        if kp:
            lines.append(f"Key points: {'; '.join(str(k)[:120] for k in kp[:4])}")
        # Dashboard
        dash = aa.get('dashboard', {})
        for cat in ['renta_variable', 'renta_fija', 'commodities_fx']:
            items = dash.get(cat, [])
            for item in items[:4]:
                if isinstance(item, dict):
                    lines.append(f"  {cat}/{item.get('asset','')}: {item.get('view','N/D')} (cambio: {item.get('cambio','=')}, conv: {item.get('conviccion','')})")
        # Risks
        riesgos = aa.get('riesgos', {})
        if isinstance(riesgos, dict):
            for r in riesgos.get('top_risks', [])[:3]:
                if isinstance(r, dict):
                    lines.append(f"  Riesgo: {r.get('nombre', '')} (prob: {r.get('probabilidad', '')}, imp: {r.get('impacto', '')})")

    return '\n'.join(lines)


AUDIT_SYSTEM_PROMPT = """\
Eres un auditor de coherencia para reportes de inversión. Tu trabajo es verificar \
que los 4 reportes mensuales (Macro, Renta Variable, Renta Fija, Asset Allocation) \
sean internamente consistentes y coherentes entre sí.

Reglas de coherencia:
1. STANCE: Si Macro es CAUTELOSO, RV y RF no deberían ser AGRESIVO sin justificación explícita.
2. POSITIONING: Los OW/UW del dashboard de Asset Allocation deben reflejar los views de RV y RF.
3. DATOS: Tasas (Fed, TPM, 10Y), spreads, e indicadores deben coincidir entre reportes.
4. RIESGOS: Los principales riesgos deben ser consistentes (mismos temas, similar probabilidad).
5. NARRATIVA: La tesis central debe ser coherente — no puede haber mensajes contradictorios.

Combinaciones válidas:
- Macro CAUTELOSO + RV CAUTELOSO + RF CONSTRUCTIVO (flight to quality) = OK
- Macro CONSTRUCTIVO + RV CONSTRUCTIVO + RF NEUTRAL = OK
- Macro CAUTELOSO + RV AGRESIVO = INCOHERENTE (a menos que RV justifique divergencia)
- AA view debe ser el promedio ponderado lógico de los 4 reportes

Responde SOLO con JSON válido (sin markdown fences):
{
  "coherence_score": 0.0-1.0,
  "stance_alignment": "COHERENTE|PARCIAL|INCOHERENTE",
  "summary": "1-2 oraciones describiendo la coherencia general",
  "flags": [
    {
      "severity": "high|medium|low",
      "type": "stance|data|positioning|narrative|risk",
      "reports": ["macro", "rv"],
      "issue": "Descripción del problema",
      "suggestion": "Cómo resolver"
    }
  ]
}

Si todo es coherente, retorna flags vacío y score >= 0.9.
Sé estricto pero razonable — divergencias justificadas no son incoherencias."""


def audit_reports(
    contents: Dict[str, Dict],
    max_tokens: int = 1000,
) -> Dict[str, Any]:
    """
    Audit coherence across the 4 report content dicts.

    Parameters
    ----------
    contents : dict
        Keys: 'macro', 'rv', 'rf', 'aa' → each a content dict from generate_all_content().
    max_tokens : int
        Max output tokens for the audit response.

    Returns
    -------
    dict with coherence_score, stance_alignment, summary, flags.
    Returns a default "skipped" result on failure.
    """

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set — report_auditor disabled")
        return _skipped("API key not available")

    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic package not installed — report_auditor disabled")
        return _skipped("anthropic package not installed")

    payload = _extract_audit_payload(contents)
    if len(payload) < 100:
        return _skipped("Insufficient report data to audit")

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            temperature=0.1,
            system=AUDIT_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Audita la coherencia de estos 4 reportes de inversión:\n\n{payload}"
            }],
        )

        raw = response.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3].strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()

        result = json.loads(raw)

        # Validate structure
        result.setdefault("coherence_score", 0.0)
        result.setdefault("stance_alignment", "UNKNOWN")
        result.setdefault("summary", "")
        result.setdefault("flags", [])
        result["status"] = "completed"

        logger.info(
            "Audit complete: score=%.2f, alignment=%s, flags=%d",
            result["coherence_score"],
            result["stance_alignment"],
            len(result["flags"]),
        )
        return result

    except json.JSONDecodeError as e:
        logger.error("Audit JSON parse error: %s", e)
        return _skipped(f"JSON parse error: {e}")
    except Exception as e:
        logger.error("Audit failed: %s", e)
        return _skipped(str(e))


def _skipped(reason: str) -> Dict[str, Any]:
    """Return a default result when audit is skipped."""
    return {
        "status": "skipped",
        "reason": reason,
        "coherence_score": None,
        "stance_alignment": None,
        "summary": f"Audit skipped: {reason}",
        "flags": [],
    }


# =========================================================================
# PHASE 4.6: REFINADOR RESOLUTION
# =========================================================================

RESOLVER_SYSTEM_PROMPT = """\
Eres el REFINADOR de Greybark Research. Se detectaron inconsistencias \
entre los 4 reportes de inversion mensuales. Tu trabajo es RESOLVER \
cada inconsistencia basandote en la recomendacion final del Council.

La recomendacion final del Council es la VERDAD. Si un reporte contradice \
la recomendacion final, ese reporte esta mal.

Para cada flag de inconsistencia, decide:
1. Cual reporte tiene razon (basandote en la recomendacion final)
2. Que debe cambiar el reporte incorrecto

Responde SOLO con JSON valido (sin markdown fences):
{
  "resolved_stance": "CAUTELOSO|CONSTRUCTIVO|NEUTRAL|AGRESIVO",
  "rationale": "1-2 oraciones explicando la postura correcta segun el council",
  "corrections": [
    {
      "report": "aa|rv|rf|macro",
      "section": "postura|dashboard|positioning|narrative",
      "directive": "Instruccion concreta para el content generator. Ej: La postura debe ser CAUTELOSO, no CONSTRUCTIVO. El dashboard debe reflejar UW en equities globales."
    }
  ]
}

Reglas:
- Maximo 4 corrections (solo las mas criticas)
- Cada directive debe ser una instruccion clara y concisa (max 80 palabras)
- Si la recomendacion final no es clara sobre un punto, usa tu juicio editorial
- NO inventes datos — solo alinea posturas y posicionamiento"""


def resolve_flags(
    audit_result: Dict[str, Any],
    council_result: Dict[str, Any],
    max_tokens: int = 800,
) -> Dict[str, Any]:
    """
    Send HIGH audit flags to the refinador for resolution.

    Returns a dict with corrections per report, or empty if no resolution needed.
    """
    flags = audit_result.get("flags", [])
    high_flags = [f for f in flags if f.get("severity") == "high"]

    if not high_flags:
        return {"status": "no_resolution_needed", "corrections": []}

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"status": "skipped", "reason": "API key not available", "corrections": []}

    try:
        import anthropic
    except ImportError:
        return {"status": "skipped", "reason": "anthropic not installed", "corrections": []}

    # Build context: council final recommendation + CIO + flags
    final_rec = council_result.get("final_recommendation", "")[:3000]
    cio = council_result.get("cio_synthesis", "")[:1500]

    flags_text = "\n".join(
        f"- [{f.get('severity','?').upper()}] ({', '.join(f.get('reports',[]))}) "
        f"{f.get('issue','')}"
        for f in high_flags
    )

    user_msg = (
        f"## RECOMENDACION FINAL DEL COUNCIL\n{final_rec}\n\n"
        f"## SINTESIS CIO\n{cio}\n\n"
        f"## FLAGS DE INCONSISTENCIA DETECTADAS\n{flags_text}"
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            temperature=0.1,
            system=RESOLVER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3].strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()

        result = json.loads(raw)
        result.setdefault("corrections", [])
        result["status"] = "resolved"

        logger.info(
            "Refinador resolved %d flags → %d corrections, stance=%s",
            len(high_flags), len(result["corrections"]),
            result.get("resolved_stance", "?"),
        )
        return result

    except Exception as e:
        logger.error("Refinador resolution failed: %s", e)
        return {"status": "error", "reason": str(e), "corrections": []}


def format_resolution(result: Dict[str, Any]) -> str:
    """Format resolution result for console output."""
    lines = []

    if result.get("status") != "resolved":
        reason = result.get("reason", result.get("status", "unknown"))
        lines.append(f"  [SKIP] Resolution: {reason}")
        return "\n".join(lines)

    lines.append(f"  Resolved stance: {result.get('resolved_stance', '?')}")
    lines.append(f"  Rationale: {result.get('rationale', '')}")

    corrections = result.get("corrections", [])
    if corrections:
        lines.append(f"  Corrections ({len(corrections)}):")
        for c in corrections:
            lines.append(f"    -> {c.get('report', '?').upper()}.{c.get('section', '?')}: {c.get('directive', '')}")
    else:
        lines.append("  No corrections needed")

    return "\n".join(lines)


def format_audit_report(result: Dict[str, Any], verbose: bool = True) -> str:
    """Format audit result for console output."""
    lines = []

    if result.get("status") == "skipped":
        lines.append(f"  [SKIP] {result.get('reason', 'unknown')}")
        return "\n".join(lines)

    score = result.get("coherence_score", 0)
    alignment = result.get("stance_alignment", "?")
    flags = result.get("flags", [])

    # Score bar
    bar_len = 20
    filled = int(score * bar_len)
    bar = "#" * filled + "-" * (bar_len - filled)
    emoji = "OK" if score >= 0.85 else ("WARN" if score >= 0.7 else "FAIL")

    lines.append(f"  Coherence: [{bar}] {score:.0%}  ({emoji})")
    lines.append(f"  Stance alignment: {alignment}")
    lines.append(f"  {result.get('summary', '')}")

    if flags:
        high = [f for f in flags if f.get("severity") == "high"]
        medium = [f for f in flags if f.get("severity") == "medium"]
        low = [f for f in flags if f.get("severity") == "low"]

        lines.append(f"  Flags: {len(high)} high, {len(medium)} medium, {len(low)} low")

        if verbose:
            for f in flags:
                sev = f.get("severity", "?").upper()
                reports = ", ".join(f.get("reports", []))
                lines.append(f"    [{sev}] ({reports}) {f.get('issue', '')}")
                if f.get("suggestion"):
                    lines.append(f"           → {f['suggestion']}")
    else:
        lines.append("  Flags: none — reports are coherent")

    return "\n".join(lines)
