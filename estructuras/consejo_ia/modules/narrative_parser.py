# -*- coding: utf-8 -*-
"""
Greybark Research - Narrative Parser (Shared Utility)
=====================================================
Parses AI Council session JSONs to extract narrative dimensions.
Used by NarrativeTracker and NarrativeDivergence modules.

NOT a module — pure utility with functions and a dataclass.
"""

import re
import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("greybark.modules.narrative_parser")

_CONSEJO_DIR = Path(__file__).parent.parent


# ── Dataclass ────────────────────────────────────────────────

@dataclass
class NarrativeDimensions:
    session_date: str               # YYYY-MM-DD
    session_timestamp: str          # ISO full
    regime_call: Optional[str]      # EXPANSION/RECESSION/STAGFLATION/SLOWDOWN/TRANSITION/LATE_CYCLE
    regime_conviction: Optional[str]  # ALTA/MEDIA/BAJA
    risk_level: Optional[str]       # ELEVATED/NORMAL/LOW/MODERATE/HIGH
    fed_stance: Optional[str]       # HAWKISH/DOVISH/NEUTRAL
    chile_positioning: Optional[str]  # OW/N/UW
    equity_conviction: Optional[str]  # ALTA/MEDIA/BAJA
    recession_probability: Optional[float]  # 0-100%
    source_file: str

    def to_dict(self) -> Dict:
        return asdict(self)


# ── Regex patterns ───────────────────────────────────────────

_RE_REGIME = re.compile(
    r'R[ÉE]GIMEN\s*(?:ACTUAL)?:?\s*\*?\*?\s*'
    r'(EXPANSI[OÓ]N|RECESI[OÓ]N|STAGFLATION|SLOWDOWN|TRANSICI[OÓ]N|LATE[\s_]?CYCLE|MODERATE)',
    re.IGNORECASE,
)

_RE_CONVICTION = re.compile(
    r'[Cc]onvicci[oó]n:?\s*\*?\*?\s*(ALTA|MEDIA|BAJA|MEDIA-ALTA|\d+/10)',
    re.IGNORECASE,
)

_RE_RISK = re.compile(
    r'[Rr]isk\s+[Aa]ssessment:?\s*\*?\*?\s*(ELEVATED|NORMAL|LOW|MODERATE|HIGH)',
    re.IGNORECASE,
)

# Also match Spanish-style risk headers: "EVALUACIÓN DE RIESGO: **ELEVADO**"
_RE_RISK_ES = re.compile(
    r'EVALUACI[OÓ]N\s+DE\s+RIESGO:?\s*\*?\*?\s*(ELEVAD[OA]|NORMAL|BAJ[OA]|MODERAD[OA]|ALT[OA])',
    re.IGNORECASE,
)

_RE_RECESSION = re.compile(
    r'[Pp]robabilidad\s+[Rr]ecesi[oó]n\s+\d+\s*[Mm](?:eses)?:?\s*(\d+)%',
    re.IGNORECASE,
)

# Fallback: "PROBABILIDAD RECESIÓN 12 MESES: 15%"
_RE_RECESSION_ALT = re.compile(
    r'RECESI[OÓ]N\s+\d+\s*MESES?:?\s*(\d+)\s*%',
    re.IGNORECASE,
)

_RE_CHILE_OW = re.compile(r'Chile[^|]*?\b(OW|UW)\b', re.IGNORECASE)

# Date from filename patterns
_RE_DATE_YYYYMMDD = re.compile(r'council_result_(\d{4})(\d{2})(\d{2})_\d+\.json')
_RE_DATE_ISO = re.compile(r'macro_council_(\d{4}-\d{2}-\d{2})\.json')

# Hawkish/dovish keyword lists
_HAWKISH_KW = [
    'hawkish', 'restrictiv', 'tightening', 'hike', 'más restrictiv',
    'menos dovish', 'inflación persistente', 'sticky inflation',
    'pausa recortes', 'pause cuts',
]
_DOVISH_KW = [
    'dovish', 'accommodat', 'easing', 'recorte', 'cut',
    'más acomodatici', 'relajamiento', 'loosening',
]


# ── Extraction functions ─────────────────────────────────────

def _extract_date_from_filename(filename: str) -> Optional[str]:
    """Extract YYYY-MM-DD from council result filename."""
    m = _RE_DATE_YYYYMMDD.match(filename)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = _RE_DATE_ISO.match(filename)
    if m:
        return m.group(1)
    return None


def _normalize_regime(raw: str) -> str:
    """Normalize regime call to English enum."""
    upper = raw.upper().strip()
    mapping = {
        'EXPANSIÓN': 'EXPANSION',
        'EXPANSION': 'EXPANSION',
        'RECESIÓN': 'RECESSION',
        'RECESSION': 'RECESSION',
        'STAGFLATION': 'STAGFLATION',
        'SLOWDOWN': 'SLOWDOWN',
        'TRANSICIÓN': 'TRANSITION',
        'TRANSITION': 'TRANSITION',
        'LATE CYCLE': 'LATE_CYCLE',
        'LATE_CYCLE': 'LATE_CYCLE',
        'MODERATE': 'MODERATE',
    }
    return mapping.get(upper, upper)


def _normalize_risk(raw: str) -> str:
    """Normalize risk level to English enum."""
    upper = raw.upper().strip()
    mapping = {
        'ELEVATED': 'ELEVATED', 'ELEVADO': 'ELEVATED', 'ELEVADA': 'ELEVATED',
        'NORMAL': 'NORMAL',
        'LOW': 'LOW', 'BAJO': 'LOW', 'BAJA': 'LOW',
        'MODERATE': 'MODERATE', 'MODERADO': 'MODERATE', 'MODERADA': 'MODERATE',
        'HIGH': 'HIGH', 'ALTO': 'HIGH', 'ALTA': 'HIGH',
    }
    return mapping.get(upper, upper)


def _normalize_conviction(raw: str) -> str:
    """Normalize conviction to ALTA/MEDIA/BAJA."""
    upper = raw.upper().strip()
    if upper in ('ALTA', 'MEDIA-ALTA'):
        return 'ALTA'
    if upper == 'MEDIA':
        return 'MEDIA'
    if upper == 'BAJA':
        return 'BAJA'
    # Handle X/10 format
    if '/' in upper:
        try:
            num = int(upper.split('/')[0])
            if num >= 7:
                return 'ALTA'
            if num >= 4:
                return 'MEDIA'
            return 'BAJA'
        except ValueError:
            pass
    return upper


def _extract_fed_stance(rf_text: str, macro_text: str) -> Optional[str]:
    """Determine Fed stance from keyword counting in RF and macro panels."""
    combined = (rf_text + " " + macro_text).lower()
    hawk_count = sum(1 for kw in _HAWKISH_KW if kw in combined)
    dove_count = sum(1 for kw in _DOVISH_KW if kw in combined)

    if hawk_count == 0 and dove_count == 0:
        return None
    if hawk_count > dove_count + 1:
        return 'HAWKISH'
    if dove_count > hawk_count + 1:
        return 'DOVISH'
    return 'NEUTRAL'


# ── Main parse function ──────────────────────────────────────

def parse_council_session(json_data: Dict, source_file: str = "") -> NarrativeDimensions:
    """
    Parse a single council session JSON and extract narrative dimensions.

    Args:
        json_data: Loaded council result JSON
        source_file: Filename for provenance

    Returns:
        NarrativeDimensions with extracted values (None for missing)
    """
    # Extract panels
    panels = json_data.get('panel_outputs', {})
    macro_text = panels.get('macro', '')
    rv_text = panels.get('rv', '')
    rf_text = panels.get('rf', '')
    risk_text = panels.get('riesgo', '')
    synthesis = json_data.get('cio_synthesis', '')
    final_rec = json_data.get('final_recommendation', '')

    all_text = f"{macro_text}\n{rv_text}\n{rf_text}\n{risk_text}\n{synthesis}\n{final_rec}"

    # Session timestamp
    metadata = json_data.get('metadata', {})
    timestamp = metadata.get('timestamp', '')

    # Date from filename or timestamp
    session_date = _extract_date_from_filename(source_file)
    if not session_date and timestamp:
        session_date = timestamp[:10]

    # 1. Regime call (search macro first, then synthesis)
    regime_call = None
    for text in [macro_text, synthesis, final_rec]:
        m = _RE_REGIME.search(text)
        if m:
            regime_call = _normalize_regime(m.group(1))
            break

    # 2. Regime conviction (from macro panel)
    regime_conviction = None
    m = _RE_CONVICTION.search(macro_text)
    if m:
        regime_conviction = _normalize_conviction(m.group(1))

    # 3. Risk level
    risk_level = None
    m = _RE_RISK.search(risk_text)
    if m:
        risk_level = _normalize_risk(m.group(1))
    else:
        m = _RE_RISK_ES.search(risk_text)
        if m:
            risk_level = _normalize_risk(m.group(1))

    # 4. Fed stance
    fed_stance = _extract_fed_stance(rf_text, macro_text)

    # 5. Chile positioning (search rv, then final_recommendation)
    chile_positioning = None
    for text in [rv_text, final_rec]:
        m = _RE_CHILE_OW.search(text)
        if m:
            chile_positioning = m.group(1).upper()
            break
    # Default to N if neither OW nor UW found but Chile is mentioned
    if chile_positioning is None and 'chile' in all_text.lower():
        chile_positioning = 'N'

    # 6. Equity conviction (from rv panel or synthesis)
    equity_conviction = None
    for text in [rv_text, synthesis]:
        m = _RE_CONVICTION.search(text)
        if m:
            equity_conviction = _normalize_conviction(m.group(1))
            break

    # 7. Recession probability
    recession_probability = None
    for text in [macro_text, synthesis]:
        m = _RE_RECESSION.search(text)
        if not m:
            m = _RE_RECESSION_ALT.search(text)
        if m:
            try:
                recession_probability = float(m.group(1))
            except ValueError:
                pass
            break

    return NarrativeDimensions(
        session_date=session_date or '',
        session_timestamp=timestamp,
        regime_call=regime_call,
        regime_conviction=regime_conviction,
        risk_level=risk_level,
        fed_stance=fed_stance,
        chile_positioning=chile_positioning,
        equity_conviction=equity_conviction,
        recession_probability=recession_probability,
        source_file=source_file,
    )


# ── Load all sessions ────────────────────────────────────────

def load_all_sessions(council_dir: Path = None) -> List[NarrativeDimensions]:
    """
    Load and parse all council session JSONs from disk.

    Args:
        council_dir: Directory containing council JSON files.
                     Defaults to consejo_ia/output/council/

    Returns:
        List of NarrativeDimensions sorted chronologically (oldest first).
    """
    if council_dir is None:
        council_dir = _CONSEJO_DIR / "output" / "council"

    if not council_dir.exists():
        logger.warning(f"Council directory not found: {council_dir}")
        return []

    sessions: List[NarrativeDimensions] = []

    for path in sorted(council_dir.glob("*.json")):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Skip files without panel_outputs (not a session file)
            if 'panel_outputs' not in data:
                continue

            nd = parse_council_session(data, source_file=path.name)
            if nd.session_date:
                sessions.append(nd)
            else:
                logger.debug(f"Skipping {path.name}: no date extracted")

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.debug(f"Skipping {path.name}: {e}")
            continue

    # Sort chronologically by date then timestamp
    sessions.sort(key=lambda s: (s.session_date, s.session_timestamp))
    return sessions


if __name__ == "__main__":
    sessions = load_all_sessions()
    print(f"{len(sessions)} sessions loaded")
    for s in sessions:
        print(f"  {s.session_date}: regime={s.regime_call}, risk={s.risk_level}, "
              f"fed={s.fed_stance}, chile={s.chile_positioning}")
