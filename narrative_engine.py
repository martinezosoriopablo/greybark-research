# -*- coding: utf-8 -*-
"""
Narrative Engine — Claude-powered narrative generation for reports.

Shared utility used by all 4 content generators (macro, RV, RF, asset allocation)
to replace hardcoded narrative text with council-aware, dynamically generated content.

Includes post-generation anti-fabrication filter (validate_narrative) that checks
AI-generated numbers against verified API data and corrects discrepancies.
"""

import os
import re
import logging
from typing import Optional, Dict, List, Tuple

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

FUNDAMENTACION — CADENA dato → interpretación → acción:
- Cada recomendación o postura DEBE seguir la cadena: DATO concreto → QUÉ SIGNIFICA \
→ QUÉ HACEMOS. Sin esta cadena, la recomendación no se incluye.
- Cada párrafo narrativo debe incluir al menos UN dato concreto (nivel, spread, \
tasa, percentil, variación) que sustente la afirmación. Si no tienes el dato, \
usa el contexto cuantitativo proporcionado.
- MAL: "Mantenemos una postura cautelosa en renta variable global."
- BIEN: "S&P a 22.1x P/E (percentil 85) con earnings revisions cayendo -1.1% \
— el precio no refleja el deterioro macro. Mantenemos <strong>UW equities</strong> \
con objetivo de reducir beta a 0.8 en los próximos 3 meses."
- MAL: "Preferimos duration larga."
- BIEN: "UST 10Y a 4.5% (percentil 82) con dot plot apuntando a 2 cortes en 6 meses \
— carry de 4.5% + potencial apreciación de capital. <strong>OW duration 5-10Y</strong>, \
target 4.0% a 6 meses."
- Especifica horizonte temporal: "esperamos X en 3-6 meses", no solo "esperamos X".
- Precisión: spreads en bps, tasas en %, P/E con 1 decimal, probabilidades en rango.

EXPLICACION DE JERGA — OBLIGATORIO:
- En la PRIMERA mención de un término técnico, agrega un paréntesis explicativo breve.
- Siguientes menciones: sin glosa.
- Términos que SIEMPRE requieren explicación en primera mención:
  - OW/UW → "sobreponderamos (OW)" / "subponderamos (UW)"
  - Duration → "duración (sensibilidad a cambios en tasas de interés)"
  - Carry → "carry (rendimiento que se obtiene por mantener la posición)"
  - Spread → "spread (diferencial de rendimiento vs bono soberano)"
  - Risk-on / risk-off → "risk-on (postura favorable a activos de riesgo)"
  - Constructivo / cauteloso → "postura constructiva (moderadamente optimista)"
  - Basis points (bps) → "128 puntos base (bps, centésimas de punto porcentual)"
  - Breakeven → "breakeven de inflación (expectativa de inflación implícita en bonos)"

RIESGO POR RECOMENDACION:
- Cada recomendación o postura incluye 1 oración de riesgo: \
"Riesgo: si [trigger cuantificado], [acción de salida específica]."
- Ejemplo: "Riesgo: si VIX supera 28 sostenido por 5 sesiones, reducimos exposición \
a equities al benchmark."

AUTOCONTENCION:
- Cada sección debe ser comprensible SIN haber leído las demás secciones del reporte.
- Incluye el mínimo contexto necesario: régimen macro actual (1 frase), postura general \
(1 frase), antes de desarrollar el análisis específico de la sección.
- Un lector que abra solo esta sección debe entender la conclusión y su fundamento.

LARGO:
- Target 120-200 palabras por sección salvo que las instrucciones indiquen otro largo.
- Secciones principales (resumen ejecutivo, conclusiones): 200-300 palabras.
- Prefiere un párrafo denso a tres párrafos diluidos.

REGLA ABSOLUTA — CERO DATOS INVENTADOS:
- NO inventes, estimes ni infieras datos numéricos que no estén en tu input.
- Solo usa datos que aparecen EXPLÍCITAMENTE en el contexto proporcionado.
- Si no hay dato → no lo menciones. Nunca escribas un número que no esté en tu input.
- Si el contexto no tiene suficiente información, di menos, no inventes más.
- "N/D" o silencio es preferible a un número fabricado.
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


# Module-level verified data — set by content generators before narrative calls
_active_verified_data: Dict[str, float] = {}


def set_verified_data(data: Dict[str, float]):
    """Set module-level verified data for anti-fabrication filter.

    Call this from a content generator before running narrative generation
    methods. All subsequent generate_narrative() calls will automatically
    validate output against this data (unless overridden by the per-call
    verified_data parameter).

    Args:
        data: dict mapping keys to verified float values from API sources.
    """
    global _active_verified_data
    _active_verified_data = data or {}
    if data:
        logger.info("ANTI-FABRICATION: verified data set with %d data points", len(data))


def clear_verified_data():
    """Clear the module-level verified data."""
    global _active_verified_data
    _active_verified_data = {}


# =============================================================================
# ANTI-FABRICATION FILTER — Post-narrative validation
# =============================================================================

# Label patterns that map text context clues to verified_data keys.
# Each entry: (regex matching surrounding text, verified_data key).
# Order matters — first match wins for a given number.
_LABEL_PATTERNS: List[Tuple[re.Pattern, str]] = [
    # P/E multiples — label is the INSTRUMENT name followed by P/E somewhere nearby.
    # The .{0,30}? allows intervening text like "a 22.1x" between instrument name
    # and the "P/E" marker. _find_label_number_pairs locates the nearest number.
    (re.compile(r'S&P(?:\s*500)?.{0,30}?(?:fwd|forward)\s*P/?E', re.IGNORECASE), 'sp500_fwd_pe'),
    (re.compile(r'S&P(?:\s*500)?.{0,30}?P/?E', re.IGNORECASE), 'sp500_pe'),
    (re.compile(r'STOXX\s*600.{0,30}?P/?E', re.IGNORECASE), 'stoxx600_pe'),
    (re.compile(r'MSCI\s*EM.{0,30}?P/?E', re.IGNORECASE), 'msci_em_pe'),
    (re.compile(r'IPSA.{0,30}?P/?E', re.IGNORECASE), 'ipsa_pe'),
    (re.compile(r'Nasdaq.{0,30}?P/?E', re.IGNORECASE), 'nasdaq_pe'),
    (re.compile(r'Nikkei.{0,30}?P/?E', re.IGNORECASE), 'nikkei_pe'),
    # Yields / rates
    (re.compile(r'(?:UST|Treasury|US)\s*10\s*[Yy]', re.IGNORECASE), 'us_10y'),
    (re.compile(r'(?:UST|Treasury|US)\s*2\s*[Yy]', re.IGNORECASE), 'us_2y'),
    (re.compile(r'(?:UST|Treasury|US)\s*30\s*[Yy]', re.IGNORECASE), 'us_30y'),
    (re.compile(r'Bund\s*10\s*[Yy]', re.IGNORECASE), 'bund_10y'),
    (re.compile(r'BTP\s*10\s*[Yy]', re.IGNORECASE), 'btp_10y'),
    (re.compile(r'BCP\s*10', re.IGNORECASE), 'bcp_10y'),
    (re.compile(r'BCP\s*5', re.IGNORECASE), 'bcp_5y'),
    (re.compile(r'BCP\s*2', re.IGNORECASE), 'bcp_2y'),
    (re.compile(r'BCU\s*10', re.IGNORECASE), 'bcu_10y'),
    (re.compile(r'BCU\s*5', re.IGNORECASE), 'bcu_5y'),
    (re.compile(r'TIPS\s*10', re.IGNORECASE), 'tips_10y'),
    # Policy rates
    (re.compile(r'(?:Fed\s*(?:Funds?)?|tasa\s*fed)', re.IGNORECASE), 'fed_rate'),
    (re.compile(r'(?:TPM|tasa\s*pol[ií]tica)', re.IGNORECASE), 'tpm'),
    (re.compile(r'BCE|ECB', re.IGNORECASE), 'ecb_rate'),
    # Inflation
    (re.compile(r'(?:Core\s*)?CPI.{0,20}?(?:YoY|interanual|anual)', re.IGNORECASE), 'core_cpi'),
    (re.compile(r'(?:headline\s*)?CPI', re.IGNORECASE), 'headline_cpi'),
    (re.compile(r'(?:Core\s*)?PCE', re.IGNORECASE), 'core_pce'),
    (re.compile(r'IPC.{0,20}?(?:Chile|YoY|anual)', re.IGNORECASE), 'chile_ipc'),
    # SOFR swap rates
    (re.compile(r'SOFR\s*(?:overnight|O/?N|rate)', re.IGNORECASE), 'sofr_rate'),
    (re.compile(r'SOFR\s*(?:swap\s*)?1\s*[Yy]', re.IGNORECASE), 'sofr_1y'),
    (re.compile(r'SOFR\s*(?:swap\s*)?2\s*[Yy]', re.IGNORECASE), 'sofr_2y'),
    (re.compile(r'SOFR\s*(?:swap\s*)?5\s*[Yy]', re.IGNORECASE), 'sofr_5y'),
    (re.compile(r'SOFR\s*(?:swap\s*)?10\s*[Yy]', re.IGNORECASE), 'sofr_10y'),
    (re.compile(r'SOFR\s*(?:swap\s*)?30\s*[Yy]', re.IGNORECASE), 'sofr_30y'),
    # Spreads (basis points)
    (re.compile(r'(?:IG|investment\s*grade)\s*(?:spread|OAS)\s*(?:total)?', re.IGNORECASE), 'ig_spread'),
    (re.compile(r'(?:HY|high\s*yield)\s*(?:spread|OAS)\s*(?:total)?', re.IGNORECASE), 'hy_spread'),
    (re.compile(r'OAS\s*(?:IG\s*)?financiero', re.IGNORECASE), 'oas_ig_financiero'),
    (re.compile(r'OAS\s*(?:IG\s*)?industrial', re.IGNORECASE), 'oas_ig_industrial'),
    (re.compile(r'OAS\s*(?:IG\s*)?(?:utilities|servicios)', re.IGNORECASE), 'oas_ig_utilities'),
    (re.compile(r'OAS\s*(?:IG\s*)?(?:tecnolog[ií]a|tech)', re.IGNORECASE), 'oas_ig_tecnologia'),
    (re.compile(r'OAS\s*(?:IG\s*)?(?:salud|health)', re.IGNORECASE), 'oas_ig_salud'),
    (re.compile(r'OAS\s*(?:IG\s*)?energ[ií]a', re.IGNORECASE), 'oas_ig_energia'),
    (re.compile(r'OAS\s*HY\s*financiero', re.IGNORECASE), 'oas_hy_financiero'),
    (re.compile(r'OAS\s*HY\s*industrial', re.IGNORECASE), 'oas_hy_industrial'),
    (re.compile(r'OAS\s*HY\s*energ[ií]a', re.IGNORECASE), 'oas_hy_energia'),
    (re.compile(r'CDS.{0,20}?(?:USA|EE\.?UU)', re.IGNORECASE), 'cds_usa'),
    (re.compile(r'CDS.{0,20}?Chile', re.IGNORECASE), 'cds_chile'),
    (re.compile(r'CDS.{0,20}?Brasil', re.IGNORECASE), 'cds_brasil'),
    (re.compile(r'CDS.{0,20}?China', re.IGNORECASE), 'cds_china'),
    (re.compile(r'EMBI', re.IGNORECASE), 'embi_spread'),
    # Volatility
    (re.compile(r'VIX', re.IGNORECASE), 'vix'),
    (re.compile(r'MOVE', re.IGNORECASE), 'move_index'),
    # Index levels
    (re.compile(r'S&P(?:\s*500)?\b(?!.{0,30}?P/?E)', re.IGNORECASE), 'sp500_level'),
    (re.compile(r'IPSA\b(?!.{0,30}?P/?E)', re.IGNORECASE), 'ipsa_level'),
    (re.compile(r'(?:cobre|copper)', re.IGNORECASE), 'copper'),
    (re.compile(r'(?:oro|gold)\b', re.IGNORECASE), 'gold'),
    (re.compile(r'(?:USD/?CLP|d[oó]lar.{0,10}?CLP)', re.IGNORECASE), 'usdclp'),
    (re.compile(r'DXY', re.IGNORECASE), 'dxy'),
    # GDP
    (re.compile(r'GDP.{0,20}?(?:US|EE\.?UU)', re.IGNORECASE), 'us_gdp'),
    (re.compile(r'PIB.{0,20}?Chile', re.IGNORECASE), 'chile_gdp'),
]

# Regex to find numeric values in narrative text.
# Matches patterns like: 4.05%, ~4.3%, 17.3x, 27.6x, 4,350, 1.76, 350bp, etc.
_NUMBER_PATTERN = re.compile(
    r'(?<![a-zA-Z/])'          # not preceded by letter or slash
    r'[~≈]?'                   # optional approximate marker
    r'(-?\d{1,5}(?:[.,]\d{1,3})?)'  # the number (group 1)
    r'\s*'
    r'(%|x|bp|bps|pb)?'       # optional unit suffix (group 2)
    r'(?![a-zA-Z]{2,})'       # not followed by a word (avoid matching inside words)
)

# Pattern to detect numbers that are part of instrument tenor labels (10Y, 2Y, 30Y, etc.)
# These should NOT be treated as data values.
_TENOR_SUFFIX = re.compile(r'\s*[Yy]\b')
# Pattern to detect numbers preceded by instrument labels (BCP 10, BCU 5, TIPS 10, etc.)
# These tenor numbers are part of the instrument name, not data values.
_INST_TENOR_PREFIX = re.compile(r'(?:BCP|BCU|BTP|Bund|TIPS)\s*$', re.IGNORECASE)


def _extract_numbers(text: str) -> List[dict]:
    """Extract all numeric values from text with their positions.

    For each number found, captures:
    - value: the parsed float
    - unit: '%', 'x', 'bp', or None
    - start/end: character positions in cleaned text
    - raw: the raw matched string for replacement

    Args:
        text: Clean text (HTML tags already stripped).

    Returns:
        List of dicts with keys: value, unit, raw, start, end.
    """
    results = []
    for m in _NUMBER_PATTERN.finditer(text):
        raw_num = m.group(1).replace(',', '')
        unit = (m.group(2) or '').lower()
        try:
            value = float(raw_num)
        except ValueError:
            continue
        # Skip trivially small or year-like numbers
        if unit == '' and 2020 <= value <= 2035:
            continue  # likely a year
        if unit == '' and value == 0:
            continue
        # Skip numbers that are part of tenor labels (e.g. "10Y", "2Y", "30Y")
        # These are instrument identifiers, not data values
        if unit == '' and _TENOR_SUFFIX.match(text[m.end():]):
            continue
        # Skip numbers preceded by instrument names (e.g. "BCP 10", "BCU 5")
        # where the number is a tenor identifier, not a value
        prefix_text = text[max(0, m.start() - 6):m.start()]
        if unit == '' and _INST_TENOR_PREFIX.search(prefix_text):
            continue
        results.append({
            'value': value,
            'unit': unit,
            'start': m.start(),
            'end': m.end(),
            'raw': m.group(0),
        })
    return results


def _find_label_number_pairs(text: str, numbers: List[dict],
                              verified_data: Dict[str, float]) -> List[Tuple[dict, str, float]]:
    """Match each label pattern in the text to its nearest number.

    Strategy: for each label pattern that appears in the text AND has a
    corresponding verified_data key, find the closest number (by character
    distance) that follows or overlaps the label. This is more robust than
    searching around each number, because it starts from the label and looks
    for the number it describes.

    Args:
        text: clean text (HTML stripped).
        numbers: list of extracted number dicts.
        verified_data: dict of verified data points.

    Returns:
        List of (number_info, key, verified_value) triples.
    """
    pairs = []
    used_numbers = set()  # track which numbers are already paired

    for pattern, key in _LABEL_PATTERNS:
        if key not in verified_data:
            continue
        for label_match in pattern.finditer(text):
            label_end = label_match.end()
            label_start = label_match.start()
            # Find the closest number AFTER (or overlapping) this label
            # within a reasonable distance (60 chars)
            best = None
            best_dist = 999
            for i, num in enumerate(numbers):
                if i in used_numbers:
                    continue
                # Number should be near the label (within 60 chars after label start)
                dist = num['start'] - label_start
                if -10 <= dist <= 60:  # allow slight overlap
                    # Prefer numbers AFTER the label
                    actual_dist = abs(num['start'] - label_end)
                    if actual_dist < best_dist:
                        best = i
                        best_dist = actual_dist
            if best is not None:
                used_numbers.add(best)
                pairs.append((numbers[best], key, verified_data[key]))
                break  # only match first occurrence of this label pattern

    return pairs


def _is_significant_discrepancy(narrative_val: float, verified_val: float,
                                 unit: str, threshold: float = 0.05) -> bool:
    """Check if the discrepancy between narrative and verified values is significant.

    Uses relative difference for most values, but absolute difference for
    small values (rates, yields) where 5% relative can be just 0.2pp.

    Args:
        narrative_val: number found in the narrative.
        verified_val: verified API value.
        unit: unit suffix ('%', 'x', 'bp', '').
        threshold: relative threshold (default 5%).

    Returns:
        True if the discrepancy exceeds the threshold.
    """
    if verified_val == 0:
        return narrative_val != 0

    abs_diff = abs(narrative_val - verified_val)
    rel_diff = abs_diff / abs(verified_val)

    # For percentages / rates: use both relative AND absolute checks
    # A rate of 4.05% vs 4.3% is ~6% relative but only 0.25pp —
    # we want to catch this since it's a meaningful difference for rates.
    if unit == '%' or unit == '':
        # For values < 10 (typical rates, yields, CPI): trigger if >0.15 absolute AND >3% relative
        if abs(verified_val) < 10:
            return abs_diff > 0.15 and rel_diff > 0.03
        # For larger values (index levels, prices): use standard relative threshold
        return rel_diff > threshold

    # For multiples (P/E): trigger if >0.5x absolute AND >3% relative
    if unit == 'x':
        return abs_diff > 0.5 and rel_diff > 0.03

    # For basis points: trigger if >15bp absolute AND >5% relative
    if unit in ('bp', 'bps', 'pb'):
        return abs_diff > 15 and rel_diff > threshold

    return rel_diff > threshold


def _format_verified_value(verified_val: float, unit: str) -> str:
    """Format a verified value for insertion into narrative text.

    Matches typical formatting conventions:
    - Percentages: 1-2 decimals
    - Multiples: 1 decimal + 'x'
    - Basis points: integer + 'bp'
    - Levels: appropriate decimal places

    Args:
        verified_val: the verified number.
        unit: the unit suffix.

    Returns:
        Formatted string.
    """
    if unit == '%':
        if abs(verified_val) >= 10:
            return f"{verified_val:.1f}%"
        return f"{verified_val:.2f}%"
    elif unit == 'x':
        return f"{verified_val:.1f}x"
    elif unit in ('bp', 'bps', 'pb'):
        return f"{int(round(verified_val))}bp"
    else:
        # General number: match precision to magnitude
        if abs(verified_val) >= 1000:
            return f"{verified_val:,.0f}"
        elif abs(verified_val) >= 10:
            return f"{verified_val:.1f}"
        else:
            return f"{verified_val:.2f}"


def validate_narrative(text: str, verified_data: Dict[str, float]) -> str:
    """Post-generation filter: validate and correct fabricated numbers.

    Scans the narrative HTML text for numeric patterns, matches each label
    (e.g. "S&P...P/E", "UST 10Y") to its nearest number, and replaces
    values that differ significantly from the verified data.

    Conservative approach: only corrects when BOTH a clear label match exists
    AND the discrepancy exceeds the threshold (>5% for most, stricter for
    small values like rates).

    Args:
        text: generated HTML narrative string.
        verified_data: dict mapping keys (e.g. 'us_10y', 'sp500_pe') to
            verified float values from API sources (yfinance, FRED, BCCh).

    Returns:
        Corrected HTML text. Unchanged if no verified_data or no issues found.
    """
    if not text or not verified_data:
        return text

    # Strip HTML tags for analysis but replace in original HTML
    clean = re.sub(r'<[^>]+>', ' ', text)

    numbers = _extract_numbers(clean)
    if not numbers:
        return text

    # Match labels to their nearest numbers
    pairs = _find_label_number_pairs(clean, numbers, verified_data)

    corrections = []

    for num_info, key, verified_val in pairs:
        narrative_val = num_info['value']
        unit = num_info['unit']

        if _is_significant_discrepancy(narrative_val, verified_val, unit):
            new_str = _format_verified_value(verified_val, unit)
            # Build context snippet for logging
            ctx_start = max(0, num_info['start'] - 30)
            ctx_end = min(len(clean), num_info['end'] + 20)
            ctx_snippet = clean[ctx_start:ctx_end].strip()

            corrections.append({
                'key': key,
                'old_val': narrative_val,
                'new_val': verified_val,
                'old_raw': num_info['raw'],
                'new_raw': new_str,
                'context_snippet': ctx_snippet,
            })
            # Log each correction
            logger.warning(
                "ANTI-FABRICATION: corrected %s: %.4g -> %.4g (key=%s, context='%s')",
                num_info['raw'], narrative_val, verified_val, key,
                ctx_snippet[:60].replace('\n', ' ')
            )

    if not corrections:
        return text

    # Apply corrections to the original HTML text.
    corrected = text
    for c in corrections:
        old_raw = c['old_raw']
        new_raw = c['new_raw']
        # Replace only the FIRST occurrence to avoid collateral damage
        # when the same number appears in different contexts
        corrected = corrected.replace(old_raw, new_raw, 1)

    n = len(corrections)
    logger.info(
        "ANTI-FABRICATION: %d correction%s applied to narrative",
        n, 's' if n != 1 else ''
    )
    return corrected


# =============================================================================
# DATA PROVENANCE — source tagging for traceability
# =============================================================================

# Module-level provenance accumulator — renderers read this after generation
_provenance_records: List[dict] = []


def get_provenance_records() -> List[dict]:
    """Get accumulated provenance records from narrative generation."""
    return list(_provenance_records)


def clear_provenance_records():
    """Clear accumulated provenance records."""
    global _provenance_records
    _provenance_records = []


def tag_verified_numbers(text: str, verified_data: Dict[str, float]) -> str:
    """Add data-source/data-verified attributes to verified numbers in HTML.

    Scans the narrative HTML for numbers that match verified data and wraps
    them in <span data-source="..." data-verified="true">...</span> tags.

    Also records provenance metadata for the hidden provenance div.

    Args:
        text: HTML narrative string (already corrected by validate_narrative).
        verified_data: dict of verified data points.

    Returns:
        HTML with tagged numbers.
    """
    if not text or not verified_data:
        return text

    clean = re.sub(r'<[^>]+>', ' ', text)
    numbers = _extract_numbers(clean)
    if not numbers:
        return text

    pairs = _find_label_number_pairs(clean, numbers, verified_data)
    if not pairs:
        return text

    # Build source mapping from _LABEL_PATTERNS key to source label
    # We tag verified numbers in the HTML
    tagged = text
    for num_info, key, verified_val in pairs:
        old_raw = num_info['raw']
        # Find the source from the manifest label patterns
        source = _key_to_source(key)
        new_html = (
            f'<span data-source="{source}" data-verified="true" '
            f'data-key="{key}">{old_raw}</span>'
        )
        # Replace first occurrence only
        tagged = tagged.replace(old_raw, new_html, 1)

        # Record provenance
        _provenance_records.append({
            'key': key,
            'value': verified_val,
            'source': source,
            'raw_text': old_raw,
        })

    return tagged


# Key → source mapping for provenance tags
_KEY_SOURCE_MAP = {
    'sp500_pe': 'yfinance:SPY', 'sp500_fwd_pe': 'yfinance:SPY',
    'stoxx600_pe': 'yfinance:VGK', 'msci_em_pe': 'yfinance:EEM',
    'ipsa_pe': 'yfinance:ECH', 'nasdaq_pe': 'yfinance:QQQ',
    'us_10y': 'FRED:DGS10', 'us_2y': 'FRED:DGS2', 'us_30y': 'FRED:DGS30',
    'bund_10y': 'BCCh:international', 'btp_10y': 'BCCh:international',
    'bcp_10y': 'BCCh:SPC', 'bcp_5y': 'BCCh:SPC', 'bcp_2y': 'BCCh:SPC',
    'bcu_10y': 'BCCh:SPC', 'bcu_5y': 'BCCh:SPC',
    'fed_rate': 'FRED:DFF', 'tpm': 'BCCh:TPM', 'ecb_rate': 'BCCh:international',
    'core_cpi': 'FRED:CPILFESL', 'headline_cpi': 'FRED:CPIAUCSL',
    'core_pce': 'FRED:PCEPILFE', 'chile_ipc': 'BCCh:IPC',
    'ig_spread': 'FRED:BAMLC0A0CM', 'hy_spread': 'FRED:BAMLH0A0HYM2',
    # BCRP EMBI spreads (Banco Central de la República de Perú)
    'embi_spread': 'BCRP:PN01138XM', 'embi_total': 'BCRP:PN01138XM',
    'embi_chile': 'BCRP:PN01132XM', 'embi_latam': 'BCRP:PN01137XM',
    'embi_peru': 'BCRP:PN01129XM', 'embi_brasil': 'BCRP:PN01131XM',
    'embi_mexico': 'BCRP:PN01135XM', 'embi_colombia': 'BCRP:PN01133XM',
    'embi_argentina': 'BCRP:PN01130XM',
    # ECB (European Central Bank SDMX API)
    'ecb_dfr': 'ECB:DFR', 'ecb_rate': 'ECB:DFR',
    'hicp_euro': 'ECB:HICP.U2', 'hicp_euro_yoy': 'ECB:HICP.U2',
    'ea_10y_yield': 'ECB:U2_10Y.YLD', 'eur_usd': 'ECB:EXR.USD.EUR',
    # IMF WEO consensus (International Monetary Fund)
    'imf_gdp_usa': 'IMF:WEO/NGDP_RPCH/USA', 'imf_gdp_chile': 'IMF:WEO/NGDP_RPCH/CHL',
    'imf_gdp_eurozone': 'IMF:WEO/NGDP_RPCH/EURO', 'imf_gdp_china': 'IMF:WEO/NGDP_RPCH/CHN',
    'imf_cpi_usa': 'IMF:WEO/PCPIPCH/USA', 'imf_cpi_chile': 'IMF:WEO/PCPIPCH/CHL',
    'consensus_imf': 'IMF:WEO',
    # BEA (Bureau of Economic Analysis)
    'gdp_qoq': 'BEA:NIPA:T10101', 'gdp_total': 'BEA:NIPA:T10101',
    'pce_headline_yoy': 'BEA:NIPA:T20804', 'pce_services_yoy': 'BEA:NIPA:T20804',
    'pce_goods_yoy': 'BEA:NIPA:T20804', 'pce_headline_mom': 'BEA:NIPA:T20807',
    'saving_rate': 'BEA:NIPA:T20600', 'personal_saving': 'BEA:NIPA:T20600',
    'corporate_profits': 'BEA:NIPA:T61600D', 'profits_yoy': 'BEA:NIPA:T61600D',
    'profits_total': 'BEA:NIPA:T61600D', 'profits_financial': 'BEA:NIPA:T61600D',
    'federal_deficit': 'BEA:NIPA:T30200', 'federal_net_lending': 'BEA:NIPA:T30200',
    # BCCh EEE Expectations (Encuesta Expectativas Economicas)
    'eee_ipc_12m': 'BCCh:EEE_IPC_12M', 'eee_ipc_24m': 'BCCh:EEE_IPC_24M',
    'eee_ipc_lp': 'BCCh:EEE_IPC_LP', 'eee_tpm_lp': 'BCCh:EEE_TPM_LP',
    'eee_tpm_11m': 'BCCh:EEE_TPM_11M', 'eee_tpm_23m': 'BCCh:EEE_TPM_23M',
    'eee_tpm_prox': 'BCCh:EEE_TPM_PROX', 'eee_pib_lp': 'BCCh:EEE_PIB_LP',
    'eee_pib_actual': 'BCCh:EEE_PIB_ACTUAL', 'eee_tcn_12m': 'BCCh:EEE_TCN_12M',
    # BCCh EOF Expectations (Encuesta Operadores Financieros)
    'eof_tpm_12m': 'BCCh:EOF_TPM_12M', 'eof_tpm_24m': 'BCCh:EOF_TPM_24M',
    'eof_ipc_12m': 'BCCh:EOF_IPC_12M',
    'eof_btp_5y': 'BCCh:EOF_BTP_5Y', 'eof_btp_10y': 'BCCh:EOF_BTP_10Y',
    'eof_btu_5y': 'BCCh:EOF_BTU_5Y', 'eof_btu_10y': 'BCCh:EOF_BTU_10Y',
    'eof_tc_28d': 'BCCh:EOF_TC_28D', 'eof_tc_3m': 'BCCh:EOF_TC_3M',
    # BCCh IMCE + IPC Detail
    'imce': 'BCCh:IMCE', 'imce_total': 'BCCh:IMCE', 'imce_sin_mineria': 'BCCh:IMCE',
    'ipc_sae': 'BCCh:IPC_SAE', 'ipc_servicios': 'BCCh:IPC_SERVICIOS',
    'ipc_bienes': 'BCCh:IPC_BIENES', 'ipc_energia': 'BCCh:IPC_ENERGIA',
    # Leading Economic Indicators (FRED)
    'lei_usa': 'FRED:USALOLITOAASTSAM', 'lei_eurozone': 'FRED:BSCICP02EZM460S',
    'cfnai': 'FRED:CFNAI', 'umich_sentiment': 'FRED:UMCSENT',
    'consumer_confidence_ez': 'FRED:CSCICP02EZM460S',
    # EPU (BCCh)
    'epu_chile': 'BCCh:F019.EPU.IND.91.M', 'epu_usa': 'BCCh:F019.EPU.IND.10.M',
    'epu_china': 'BCCh:F019.EPU.IND.CHN.M', 'epu_europa': 'BCCh:F019.EPU.IND.94.M',
    'epu_global': 'BCCh:F019.EPU.IND.90.M', 'epu_uk': 'BCCh:F019.EPU.IND.UK.M',
    'move': 'BCCh:F019.MOVE.IND.90.D',
    # OECD KEI
    'oecd_cli': 'OECD:KEI:LI', 'oecd_cli_usa': 'OECD:KEI:LI',
    'oecd_cli_chl': 'OECD:KEI:LI', 'oecd_cli_chn': 'OECD:KEI:LI',
    'oecd_cci': 'OECD:KEI:CCICP', 'oecd_bci': 'OECD:KEI:BCICP',
    'oecd_unemployment': 'OECD:KEI:UNEMP', 'oecd_cpi': 'OECD:KEI:CP',
    'oecd_rates': 'OECD:KEI:IR3TIB+IRLT',
    # NY Fed
    'sofr': 'NYFed:SOFR', 'effr': 'NYFed:EFFR', 'obfr': 'NYFed:OBFR',
    'gscpi': 'NYFed:GSCPI', 'nyfed_gscpi': 'NYFed:GSCPI',
    'rstar': 'NYFed:Rstar', 'nyfed_rstar': 'NYFed:Rstar',
    'term_premium': 'FRED:ACMTermPremia', 'tp_10y': 'FRED:THREEFYTP10',
    'tp_2y': 'FRED:THREEFYTP2', 'tp_5y': 'FRED:THREEFYTP5',
    # Other
    'vix': 'yfinance:^VIX', 'move_index': 'FRED:MOVE',
    'sp500_level': 'yfinance:SPY', 'ipsa_level': 'BCCh:IPSA',
    'copper': 'BCCh:commodities', 'gold': 'BCCh:commodities',
    'usdclp': 'BCCh:FX', 'dxy': 'yfinance:DX-Y.NYB',
    'us_gdp': 'FRED:GDPC1', 'chile_gdp': 'BCCh:PIB',
    'tips_10y': 'FRED:DFII10', 'breakeven_10y': 'FRED:T10YIE',
    # SOFR Swap Curve (Bloomberg)
    'sofr_rate': 'Bloomberg:SOFRRATE', 'sofr_1y': 'Bloomberg:USOSFR1',
    'sofr_2y': 'Bloomberg:USOSFR2', 'sofr_5y': 'Bloomberg:USOSFR5',
    'sofr_10y': 'Bloomberg:USOSFR10', 'sofr_30y': 'Bloomberg:USOSFR30',
    # Bloomberg OAS Sector Spreads
    'oas_ig_financiero': 'Bloomberg:USOAIGFI', 'oas_ig_industrial': 'Bloomberg:USOAIGIN',
    'oas_ig_utilities': 'Bloomberg:USOAIGUT', 'oas_ig_tecnologia': 'Bloomberg:USOAIGTC',
    'oas_ig_salud': 'Bloomberg:USOAIGHC', 'oas_ig_energia': 'Bloomberg:USOAIGEN',
    'oas_hy_financiero': 'Bloomberg:USOHHYFI', 'oas_hy_industrial': 'Bloomberg:USOHHYIN',
    'oas_hy_energia': 'Bloomberg:USOHHYEN',
    # Bloomberg CDS
    'cds_usa': 'Bloomberg:CDS_USA', 'cds_chile': 'Bloomberg:CDS_Chile',
    'cds_brasil': 'Bloomberg:CDS_Brasil', 'cds_china': 'Bloomberg:CDS_China',
}


def _key_to_source(key: str) -> str:
    """Map a verified_data key to its API source string."""
    return _KEY_SOURCE_MAP.get(key, f'verified:{key}')


# =============================================================================
# VERIFIED DATA BUILDERS — helpers for content generators
# =============================================================================

def build_verified_data_rv(market_data: dict) -> Dict[str, float]:
    """Build verified_data dict from RV content generator's market_data.

    Extracts P/E multiples, index levels, and related metrics from the
    market_data structure used by RVContentGenerator.

    Args:
        market_data: the market_data dict passed to RVContentGenerator.

    Returns:
        Dict of verified data points suitable for validate_narrative().
    """
    vd: Dict[str, float] = {}
    if not market_data:
        return vd

    def _safe(val):
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    # Valuations by region
    valuations = market_data.get('valuations', {})
    for region_key, vd_key_pe in [
        ('us', 'sp500_pe'), ('europe', 'stoxx600_pe'),
        ('em', 'msci_em_pe'), ('chile', 'ipsa_pe'),
    ]:
        v = valuations.get(region_key, {})
        pe = _safe(v.get('pe_trailing') or v.get('pe') or v.get('pe_fwd'))
        if pe is not None:
            vd[vd_key_pe] = pe
        fwd_pe = _safe(v.get('pe_fwd') or v.get('forward_pe'))
        if fwd_pe is not None and region_key == 'us':
            vd['sp500_fwd_pe'] = fwd_pe

    # BCCh indices
    bcch = market_data.get('bcch_indices', {})
    for idx_key, vd_key in [
        ('ipsa', 'ipsa_level'), ('copper', 'copper'),
        ('gold', 'gold'), ('usdclp', 'usdclp'),
    ]:
        val = _safe(bcch.get(idx_key))
        if val is not None:
            vd[vd_key] = val

    # Risk metrics
    risk = market_data.get('risk', {})
    vix = _safe(risk.get('vix') or risk.get('vix_current'))
    if vix is not None:
        vd['vix'] = vix

    return vd


def build_verified_data_rf(market_data: dict) -> Dict[str, float]:
    """Build verified_data dict from RF content generator's market_data.

    Extracts yields, spreads, policy rates, and inflation data from the
    market_data structure used by RFContentGenerator.

    Args:
        market_data: the market_data dict passed to RFContentGenerator.

    Returns:
        Dict of verified data points suitable for validate_narrative().
    """
    vd: Dict[str, float] = {}
    if not market_data:
        return vd

    def _safe(val):
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    def _deep_get(d, *keys):
        for k in keys:
            if not isinstance(d, dict) or k not in d:
                return None
            d = d[k]
        if isinstance(d, dict) and 'error' in d:
            return None
        return d

    # Yield curve
    yc = market_data.get('yield_curve', {})
    curve = yc.get('current_curve', {})
    yields_alt = yc.get('yields', {})
    for tenor, vd_key in [('10Y', 'us_10y'), ('2Y', 'us_2y'), ('30Y', 'us_30y')]:
        val = _safe(curve.get(tenor)) or _safe(yields_alt.get(f'DGS{tenor.replace("Y", "")}'))
        if val is not None:
            vd[vd_key] = val

    # Credit spreads
    cs = market_data.get('credit_spreads', {})
    ig = _safe(_deep_get(cs, 'ig_breakdown', 'total', 'current_bps'))
    if ig is not None:
        vd['ig_spread'] = ig
    hy = _safe(_deep_get(cs, 'hy_breakdown', 'total', 'current_bps'))
    if hy is not None:
        vd['hy_spread'] = hy

    # Policy rates
    cr = market_data.get('chile_rates', {})
    tpm = _safe(_deep_get(cr, 'tpm', 'current'))
    if tpm is not None:
        vd['tpm'] = tpm
    pr = cr.get('policy_rates', {})
    for rate_key, vd_key in [('fed', 'fed_rate'), ('ecb', 'ecb_rate')]:
        val = _safe(pr.get(rate_key))
        if val is not None:
            vd[vd_key] = val

    # International yields
    intl = market_data.get('international_yields', {})
    for country, vd_key in [('germany', 'bund_10y'), ('italy', 'btp_10y')]:
        val = _safe(_deep_get(intl, country, 'yield_10y'))
        if val is not None:
            vd[vd_key] = val

    # Chile yields (BCP/BCU)
    cl_y = market_data.get('chile_yields', {})
    for inst, tenors in [('bcp', [('10', 'bcp_10y'), ('5', 'bcp_5y'), ('2', 'bcp_2y')]),
                          ('bcu', [('10', 'bcu_10y'), ('5', 'bcu_5y')])]:
        for tenor, vd_key in tenors:
            val = _safe(_deep_get(cl_y, inst, tenor, 'yield'))
            if val is not None:
                vd[vd_key] = val

    # Inflation / breakevens
    infl = market_data.get('inflation', {})
    for infl_key, vd_key in [
        ('tips_10y', 'tips_10y'), ('breakeven_10y', 'breakeven_10y'),
        ('core_cpi', 'core_cpi'), ('headline_cpi', 'headline_cpi'),
        ('core_pce', 'core_pce'),
    ]:
        val = _safe(infl.get(infl_key))
        if val is not None:
            vd[vd_key] = val

    return vd


def build_verified_data_macro(quant_data: dict, data_provider=None) -> Dict[str, float]:
    """Build verified_data dict from Macro content generator's data sources.

    Extracts GDP, inflation, and policy rate data from the quant_data dict
    and optional ChartDataProvider.

    Args:
        quant_data: the quant_data dict passed to MacroContentGenerator.
        data_provider: optional ChartDataProvider instance for BCCh data.

    Returns:
        Dict of verified data points suitable for validate_narrative().
    """
    vd: Dict[str, float] = {}
    if not quant_data:
        return vd

    def _safe(val):
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    def _deep_get(d, *keys):
        for k in keys:
            if not isinstance(d, dict) or k not in d:
                return None
            d = d[k]
        return d

    # USA macro
    us_gdp = _safe(_deep_get(quant_data, 'macro_usa', 'gdp'))
    if us_gdp is not None:
        vd['us_gdp'] = us_gdp
    core_cpi = _safe(_deep_get(quant_data, 'macro_usa', 'core_cpi'))
    if core_cpi is not None:
        vd['core_cpi'] = core_cpi

    # Chile
    chile_tpm = _safe(_deep_get(quant_data, 'chile', 'tpm'))
    if chile_tpm is not None:
        vd['tpm'] = chile_tpm
    chile_ipc = _safe(_deep_get(quant_data, 'chile', 'ipc_yoy'))
    if chile_ipc is not None:
        vd['chile_ipc'] = chile_ipc
    chile_gdp = _safe(_deep_get(quant_data, 'chile', 'pib_yoy'))
    if chile_gdp is not None:
        vd['chile_gdp'] = chile_gdp

    # Try data_provider for additional real-time data
    if data_provider:
        try:
            usa = data_provider.get_usa_latest()
            if usa:
                for k, vd_k in [('fed_rate', 'fed_rate'), ('cpi_yoy', 'headline_cpi'),
                                  ('core_cpi', 'core_cpi'), ('pce_core', 'core_pce')]:
                    val = _safe(usa.get(k))
                    if val is not None:
                        vd[vd_k] = val
        except Exception:
            pass
        try:
            cl = data_provider.get_chile_latest()
            if cl:
                for k, vd_k in [('tpm', 'tpm'), ('ipc_yoy', 'chile_ipc'),
                                  ('copper', 'copper'), ('usdclp', 'usdclp')]:
                    val = _safe(cl.get(k))
                    if val is not None:
                        vd[vd_k] = val
        except Exception:
            pass

    return vd


def build_verified_data_aa(quant_data: dict) -> Dict[str, float]:
    """Build verified_data dict from Asset Allocation content generator's data.

    Extracts rates, spreads, VIX, and macro data from the quant_data dict
    used by AssetAllocationContentGenerator.

    Args:
        quant_data: the quant_data dict passed to AssetAllocationContentGenerator.

    Returns:
        Dict of verified data points suitable for validate_narrative().
    """
    vd: Dict[str, float] = {}
    if not quant_data:
        return vd

    def _safe(val):
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    def _deep_get(d, *keys):
        for k in keys:
            if not isinstance(d, dict) or k not in d:
                return None
            d = d[k]
        return d

    # Macro USA
    core_cpi = _safe(_deep_get(quant_data, 'macro_usa', 'core_cpi'))
    if core_cpi is not None:
        vd['core_cpi'] = core_cpi
    us_gdp = _safe(_deep_get(quant_data, 'macro_usa', 'gdp'))
    if us_gdp is not None:
        vd['us_gdp'] = us_gdp

    # Chile
    tpm = _safe(_deep_get(quant_data, 'chile', 'tpm'))
    if tpm is not None:
        vd['tpm'] = tpm
    ipc = _safe(_deep_get(quant_data, 'chile', 'ipc_yoy'))
    if ipc is not None:
        vd['chile_ipc'] = ipc

    # Credit spreads
    ig = _safe(_deep_get(quant_data, 'credit_spreads', 'ig_breakdown', 'total', 'current_bps'))
    if ig is not None:
        vd['ig_spread'] = ig
    hy = _safe(_deep_get(quant_data, 'credit_spreads', 'hy_breakdown', 'total', 'current_bps'))
    if hy is not None:
        vd['hy_spread'] = hy

    # Duration / yields
    dur = quant_data.get('duration', {})
    if isinstance(dur, dict):
        ust_10y = _safe(dur.get('ust_10y'))
        if ust_10y is not None:
            vd['us_10y'] = ust_10y

    # VIX
    vix_data = quant_data.get('vix', {})
    if isinstance(vix_data, dict):
        vix = _safe(vix_data.get('current'))
        if vix is not None:
            vd['vix'] = vix

    # TPM expectations
    tpm_exp = quant_data.get('tpm_expectations', {})
    if isinstance(tpm_exp, dict):
        tpm_cur = _safe(tpm_exp.get('current'))
        if tpm_cur is not None and 'tpm' not in vd:
            vd['tpm'] = tpm_cur

    return vd


def generate_narrative(
    section_name: str,
    prompt: str,
    council_context: str,
    quant_context: str = "",
    company_name: str = "",
    max_tokens: int = 1000,
    temperature: float = 0.3,
    correction_directive: str = "",
    verified_data: Dict[str, float] = None,
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
        correction_directive: Optional correction from refinador.
        verified_data: Optional dict of verified numeric data from API sources
            (e.g. {'us_10y': 4.05, 'sp500_pe': 27.6}). When provided, the
            generated text is post-filtered to correct fabricated numbers.

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

        # Post-generation anti-fabrication filter
        # Use per-call verified_data if provided, else fall back to module-level
        effective_verified = verified_data if verified_data is not None else _active_verified_data
        if effective_verified and text:
            text = validate_narrative(text, effective_verified)
            # Add data-source tags for traceability
            text = tag_verified_numbers(text, effective_verified)

        return text
    except Exception as e:
        logger.error(f"narrative_engine: {section_name} failed — {e}")
        return ""
