# -*- coding: utf-8 -*-
"""
Council Parser — Structured Data Extraction from Council Output
================================================================

Parses [BLOQUE: X] delimited sections from council agent outputs.
Provides typed accessors for content generators to use instead of hardcoded data.

Fallback behavior: returns None (never "N/D" — that's the generator's job).

Usage:
    from council_parser import CouncilParser

    parser = CouncilParser(council_result)
    stance = parser.get_macro_stance()          # "CONSTRUCTIVO" | None
    risks = parser.get_risk_assessment()        # [{'risk': ..., 'probability': ...}] | None
    equities = parser.get_equity_views()        # {region: {view, conviction, rationale}} | None

Sources are searched in priority order:
    1. final_recommendation (refinador output — highest authority)
    2. cio_synthesis
    3. panel_outputs (macro, rv, rf, riesgo, geo)

First occurrence wins — refinador/CIO blocks take priority over panel blocks.
"""

import re
from typing import Dict, List, Optional, Any


class CouncilParser:
    """Extracts structured data from council output."""

    def __init__(self, council_result: Dict = None):
        self._result = council_result or {}
        self._final = self._result.get('final_recommendation', '')
        self._cio = self._result.get('cio_synthesis', '')
        self._panels = self._result.get('panel_outputs', {})
        self._blocks_cache: Dict[str, str] = {}
        self._parse_all_blocks()

    def _parse_all_blocks(self):
        """Parse all [BLOQUE: X] sections from all outputs."""
        # Search in final_recommendation, cio_synthesis, and all panel outputs
        sources = [self._final, self._cio]
        for agent_name, text in self._panels.items():
            sources.append(text)

        for text in sources:
            if not text:
                continue
            # Pattern: [BLOQUE: NAME] followed by content until next [BLOQUE: or end
            pattern = r'\[BLOQUE:\s*([^\]]+)\](.*?)(?=\[BLOQUE:|$)'
            for match in re.finditer(pattern, text, re.DOTALL):
                block_name = match.group(1).strip().upper()
                block_content = match.group(2).strip()
                # Don't overwrite — first occurrence (refinador/final) takes priority
                if block_name not in self._blocks_cache:
                    self._blocks_cache[block_name] = block_content

    def _get_block(self, name: str) -> Optional[str]:
        """Get raw content of a named block."""
        return self._blocks_cache.get(name.upper())

    # =========================================================================
    # MACRO
    # =========================================================================

    def get_macro_stance(self) -> Optional[str]:
        """Extract macro stance: CONSTRUCTIVO/CAUTELOSO/NEUTRAL/AGRESIVO."""
        block = self._get_block('POSTURA_MACRO')
        if block:
            match = re.search(
                r'Postura:\s*(CONSTRUCTIVO|CAUTELOSO|NEUTRAL|AGRESIVO)',
                block, re.IGNORECASE
            )
            if match:
                return match.group(1).upper()
        return None

    def get_scenario_probs(self) -> Optional[Dict]:
        """Extract scenario probabilities with description.

        Returns:
            {scenario_key: {'prob': float, 'name': str, 'description': str}} or None.
            prob is 0.0-1.0.
        """
        block = self._get_block('ESCENARIOS')
        if not block:
            return None

        scenarios = {}
        # Pattern: - Base/Alternativo: {name}, probabilidad {X}%, rest of line
        pattern = (
            r'-\s*(?:Base|Alternativo[_\s]*\d*|Upside|Downside)'
            r'[:\s]*([^,]+),\s*probabilidad\s+(\d+)%'
            r'(?:,\s*(.+?))?$'
        )
        for match in re.finditer(pattern, block, re.IGNORECASE | re.MULTILINE):
            name = match.group(1).strip()
            prob = float(match.group(2)) / 100.0
            rest = (match.group(3) or '').strip()
            # Build description from dato_soporte and riesgo fields
            desc = rest.replace('dato_soporte:', 'Soporte:').replace('riesgo:', 'Riesgo:') if rest else ''
            # Normalize scenario name
            key = name.lower().replace(' ', '_')
            scenarios[key] = {'prob': prob, 'name': name, 'description': desc}

        return scenarios if scenarios else None

    # =========================================================================
    # RISK
    # =========================================================================

    def get_risk_assessment(self) -> Optional[List[Dict]]:
        """Extract risk matrix.

        Returns:
            [{'risk': str, 'probability': str, 'impact': str, 'horizon': str}]
            or None.
        """
        block = self._get_block('RISK_MATRIX')
        if not block:
            return None

        risks = []
        # Pattern: {name}: {X}%, {ALTO|MEDIO|BAJO}, {horizon}
        pattern = r'([^:\n]+):\s*(\d+)%,\s*(ALTO|MEDIO|BAJO),\s*(.+?)(?:\n|$)'
        for match in re.finditer(pattern, block, re.IGNORECASE):
            risks.append({
                'risk': match.group(1).strip(),
                'probability': f"{match.group(2)}%",
                'impact': match.group(3).upper(),
                'horizon': match.group(4).strip(),
            })

        return risks if risks else None

    def get_geopolitical_risks(self) -> Optional[List[Dict]]:
        """Extract geopolitical risks.

        Returns:
            [{'event': str, 'probability': str, 'impact': str}] or None.
        """
        block = self._get_block('GEO_RISKS')
        if not block:
            return None

        risks = []
        pattern = r'([^:\n]+?):\s*(\d+)%,\s*(.+?)(?:\n|$)'
        for match in re.finditer(pattern, block):
            risks.append({
                'event': match.group(1).strip(),
                'probability': f"{match.group(2)}%",
                'impact': match.group(3).strip(),
            })

        return risks if risks else None

    # =========================================================================
    # EQUITY / RV
    # =========================================================================

    def get_equity_views(self) -> Optional[Dict]:
        """Extract equity views by region.

        Returns:
            {region: {'view': 'OW'|'NEUTRAL'|'UW',
                      'conviction': 'ALTA'|'MEDIA'|'BAJA',
                      'rationale': str}}
            or None.
        """
        block = self._get_block('EQUITY_VIEWS')
        if not block:
            return None

        views = {}
        # Pattern: Region: {OW|NEUTRAL|UW}, {ALTA|MEDIA|BAJA}, {rationale}
        pattern = r'(\w[\w\s]*?):\s*(OW|NEUTRAL|UW),\s*(ALTA|MEDIA|BAJA),\s*(.+?)(?:\n|$)'
        for match in re.finditer(pattern, block, re.IGNORECASE):
            region = match.group(1).strip()
            views[region.lower()] = {
                'view': match.group(2).upper(),
                'conviction': match.group(3).upper(),
                'rationale': match.group(4).strip(),
            }

        return views if views else None

    def get_sector_views(self) -> Optional[Dict]:
        """Extract sector views.

        Returns:
            {sector: {'view': 'OW'|'NEUTRAL'|'UW', 'rationale': str}}
            or None.
        """
        block = self._get_block('SECTOR_VIEWS')
        if not block:
            return None

        views = {}
        pattern = r'(\w[\w\s/&]*?):\s*(OW|NEUTRAL|UW),\s*(.+?)(?:\n|$)'
        for match in re.finditer(pattern, block, re.IGNORECASE):
            sector = match.group(1).strip()
            views[sector.lower()] = {
                'view': match.group(2).upper(),
                'rationale': match.group(3).strip(),
            }

        return views if views else None

    def get_factor_views(self) -> Optional[Dict]:
        """Extract factor/style views (Quality, Momentum, Value, Growth, Size).

        Returns:
            {factor_lower: {'view': 'OW'|'NEUTRAL'|'UW', 'rationale': str}}
            or None.
        """
        block = self._get_block('FACTOR_VIEWS')
        if not block:
            return None

        views = {}
        pattern = r'(\w[\w\s/&]*?):\s*(OW|NEUTRAL|UW),\s*(.+?)(?:\n|$)'
        for match in re.finditer(pattern, block, re.IGNORECASE):
            factor = match.group(1).strip()
            views[factor.lower()] = {
                'view': match.group(2).upper(),
                'rationale': match.group(3).strip(),
            }

        return views if views else None

    # =========================================================================
    # FIXED INCOME / RF
    # =========================================================================

    def get_fi_views(self) -> Optional[Dict]:
        """Extract fixed income positioning.

        Returns:
            {segment: {'view': 'OW'|'NEUTRAL'|'UW',
                       'duration': 'CORTA'|'NEUTRAL'|'LARGA',
                       'rationale': str}}
            or None.
        """
        block = self._get_block('FI_POSITIONING')
        if not block:
            return None

        views = {}
        # Pattern: Segment: {OW|NEUTRAL|UW}, {CORTA|NEUTRAL|LARGA}, {rationale}
        pattern = r'([^:\n]+?):\s*(OW|NEUTRAL|UW),\s*(CORTA|NEUTRAL|LARGA),\s*(.+?)(?:\n|$)'
        for match in re.finditer(pattern, block, re.IGNORECASE):
            segment = match.group(1).strip()
            views[segment.lower()] = {
                'view': match.group(2).upper(),
                'duration': match.group(3).upper(),
                'rationale': match.group(4).strip(),
            }

        return views if views else None

    def get_duration_stance(self) -> Optional[Dict]:
        """Extract duration stance.

        Returns:
            {'stance': str, 'benchmark': float, 'recommendation': float}
            or None. Keys present only if found in block.
        """
        block = self._get_block('DURATION')
        if not block:
            return None

        result = {}
        stance_m = re.search(r'Stance:\s*(.+?)(?:\n|$)', block)
        if stance_m:
            result['stance'] = stance_m.group(1).strip()
        bench_m = re.search(r'Benchmark:\s*([\d.]+)', block)
        if bench_m:
            result['benchmark'] = float(bench_m.group(1))
        rec_m = re.search(r'Recomendaci[oó]n:\s*([\d.]+)', block)
        if rec_m:
            result['recommendation'] = float(rec_m.group(1))

        return result if result else None

    # =========================================================================
    # FX
    # =========================================================================

    def get_fx_views(self) -> Optional[Dict]:
        """Extract FX views.

        Returns:
            {pair: {'view': 'ALCISTA'|'BAJISTA'|'NEUTRAL', 'rationale': str}}
            or None.
        """
        block = self._get_block('FX_VIEWS')
        if not block:
            return None

        views = {}
        pattern = r'([A-Z]{3}/[A-Z]{3}):\s*(ALCISTA|BAJISTA|NEUTRAL),\s*(.+?)(?:\n|$)'
        for match in re.finditer(pattern, block, re.IGNORECASE):
            pair = match.group(1).upper()
            views[pair] = {
                'view': match.group(2).upper(),
                'rationale': match.group(3).strip(),
            }

        return views if views else None

    # =========================================================================
    # ALLOCATION
    # =========================================================================

    def get_regional_allocation(self) -> Optional[Dict]:
        """Extract regional allocation weights.

        Returns:
            {region: {'weight': str, 'vs_benchmark': str, 'rationale': str}}
            or None.
        """
        block = self._get_block('ALLOCATION')
        if not block:
            return None

        alloc = {}
        pattern = r'([^:\n|]+?):\s*(\d+(?:\.\d+)?%?),\s*([^,\n]+),\s*(.+?)(?:\n|$)'
        for match in re.finditer(pattern, block):
            region = match.group(1).strip()
            alloc[region.lower()] = {
                'weight': match.group(2).strip(),
                'vs_benchmark': match.group(3).strip(),
                'rationale': match.group(4).strip(),
            }

        return alloc if alloc else None

    def get_chile_view(self) -> Optional[Dict]:
        """Extract Chile-specific view from allocation or panels.

        Returns:
            {'view': str, 'tpm_path': str|None, 'rationale': str} or None.
        """
        alloc = self.get_regional_allocation()
        if alloc and 'chile' in alloc:
            return alloc['chile']

        # Fallback: search in macro panel for Chile-specific guidance
        macro = self._panels.get('macro', '')
        if 'chile' in macro.lower():
            # Extract a sentence about Chile
            pattern = r'(?:Chile|BCCh|TPM)[^.]*\.'
            matches = re.findall(pattern, macro, re.IGNORECASE)
            if matches:
                return {
                    'view': matches[0],
                    'tpm_path': None,
                    'rationale': matches[0],
                }

        return None

    # =========================================================================
    # TEXT MINING FALLBACKS
    # =========================================================================

    def _all_text(self) -> str:
        """Return concatenated text from all sources for text mining."""
        parts = [self._final, self._cio]
        parts.extend(self._panels.values())
        return '\n'.join(p for p in parts if p)

    def _has_council_text(self) -> bool:
        """Check if we have any council output text at all."""
        return bool(self._final or self._cio or any(self._panels.values()))

    def search_region_view(self, region: str) -> Optional[Dict]:
        """Text-mine a region's view/conviction from raw council text.

        Searches all council outputs for OW/UW/NEUTRAL mentions near
        the region name. Returns best match or None.
        """
        text = self._all_text()
        if not text:
            return None

        # Map region aliases
        aliases = {
            'usa': ['USA', 'Estados Unidos', 'EE\\.?UU', 'US equity', 'US Large'],
            'estados unidos': ['USA', 'Estados Unidos', 'EE\\.?UU', 'US equity'],
            'europa': ['Europa', 'Europe', 'Eurozon', 'MSCI Europe'],
            'china': ['China', 'MSCI China', 'Hang Seng', 'CSI'],
            'chile': ['Chile', 'IPSA', 'Santiago'],
            'brasil': ['Brasil', 'Brazil', 'Bovespa'],
            'mexico': ['M[eé]xico', 'Mexico', 'IPC M[eé]x'],
            'em': ['Emergentes', 'EM', 'Emerging'],
        }

        region_patterns = aliases.get(region.lower(), [region])

        for rp in region_patterns:
            # Reverse first (more precise): "OW/UW {region}" within ~60 chars, same sentence
            pattern_rev = rf'\b(OW|OVERWEIGHT|UW|UNDERWEIGHT|NEUTRAL)\b[^.;\n]{{0,60}}?(?:{rp})\b'
            m2 = re.search(pattern_rev, text, re.IGNORECASE)
            if m2:
                raw_view = m2.group(1).upper()
                view = {'OVERWEIGHT': 'OW', 'UNDERWEIGHT': 'UW'}.get(raw_view, raw_view)
                conv = self._find_conviction_near(text, m2.start(), m2.end())
                return {'view': view, 'conviction': conv, 'rationale': 'Extracted from council text'}

            # Forward: "{region}...OW/UW/NEUTRAL" within same sentence (~60 chars)
            pattern = rf'(?:{rp})\b[^.;\n]{{0,60}}?\b(OW|OVERWEIGHT|UW|UNDERWEIGHT|NEUTRAL)\b'
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                raw_view = m.group(1).upper()
                view = {'OVERWEIGHT': 'OW', 'UNDERWEIGHT': 'UW'}.get(raw_view, raw_view)
                conv = self._find_conviction_near(text, m.start(), m.end())
                return {'view': view, 'conviction': conv, 'rationale': 'Extracted from council text'}

        return None

    def _find_conviction_near(self, text: str, start: int, end: int) -> str:
        """Find conviction level near a match position."""
        window = text[max(0, start - 80):min(len(text), end + 80)]
        m = re.search(r'\b(ALTA|MEDIA|BAJA|HIGH|MEDIUM|LOW)\b', window, re.IGNORECASE)
        if m:
            raw = m.group(1).upper()
            return {'HIGH': 'ALTA', 'MEDIUM': 'MEDIA', 'LOW': 'BAJA'}.get(raw, raw)
        return 'MEDIA'  # default when council text exists but conviction not explicit

    def search_duration_view(self) -> Optional[str]:
        """Text-mine duration stance from council text."""
        text = self._all_text()
        if not text:
            return None

        # Look for duration-related keywords
        patterns = [
            (r'\bduraci[oó]n\s+corta\b', 'CORTA'),
            (r'\bduration\s+corta\b', 'CORTA'),
            (r'\bshort\s+duration\b', 'CORTA'),
            (r'\binfraponderar\s+duraci[oó]n\b', 'CORTA'),
            (r'\bduraci[oó]n\s+larga\b', 'LARGA'),
            (r'\bduration\s+larga\b', 'LARGA'),
            (r'\blong\s+duration\b', 'LARGA'),
            (r'\bsobreponderar\s+duraci[oó]n\b', 'LARGA'),
            (r'\bduraci[oó]n\s+neutral\b', 'NEUTRAL'),
            (r'\bduration\s+neutral\b', 'NEUTRAL'),
        ]
        for pat, stance in patterns:
            if re.search(pat, text, re.IGNORECASE):
                return stance
        return None

    def search_credit_view(self, segment: str) -> Optional[str]:
        """Text-mine credit segment view (IG/HY) from council text."""
        text = self._all_text()
        if not text:
            return None

        seg_aliases = {
            'ig': ['IG', 'Investment Grade', 'grado de inversi[oó]n'],
            'hy': ['HY', 'High Yield', 'alto rendimiento'],
        }
        aliases = seg_aliases.get(segment.lower(), [segment])

        for alias in aliases:
            pattern = rf'(?:{alias})\b.{{0,80}}?\b(OW|OVERWEIGHT|UW|UNDERWEIGHT|NEUTRAL)\b'
            m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if m:
                raw = m.group(1).upper()
                return {'OVERWEIGHT': 'OW', 'UNDERWEIGHT': 'UW'}.get(raw, raw)

            # Reverse
            pattern_rev = rf'\b(OW|OVERWEIGHT|UW|UNDERWEIGHT|NEUTRAL)\b.{{0,80}}?(?:{alias})\b'
            m2 = re.search(pattern_rev, text, re.IGNORECASE | re.DOTALL)
            if m2:
                raw = m2.group(1).upper()
                return {'OVERWEIGHT': 'OW', 'UNDERWEIGHT': 'UW'}.get(raw, raw)

        return None

    def search_fx_pair_view(self, pair: str = 'USD/CLP') -> Optional[Dict]:
        """Text-mine FX pair view from council text."""
        text = self._all_text()
        if not text:
            return None

        # Search for pair mentions with directional words
        patterns = [
            (rf'{pair}.{{0,80}}?(ALCISTA|BULLISH|fortalec)', 'ALCISTA'),
            (rf'{pair}.{{0,80}}?(BAJISTA|BEARISH|debilit)', 'BAJISTA'),
            (rf'{pair}.{{0,80}}?(NEUTRAL|rango|lateral)', 'NEUTRAL'),
        ]
        for pat, view in patterns:
            if re.search(pat, text, re.IGNORECASE | re.DOTALL):
                return {'view': view, 'rationale': 'Extracted from council text'}

        # Specific DXY patterns
        if 'DXY' in pair.upper() or pair == 'USD':
            dxy_patterns = [
                (r'd[oó]lar.{0,60}?(fuerte|fortalec|alcista)', 'ALCISTA'),
                (r'd[oó]lar.{0,60}?(d[eé]bil|debilit|bajista)', 'BAJISTA'),
                (r'DXY.{0,60}?(sube|alza|alcista)', 'ALCISTA'),
                (r'DXY.{0,60}?(baja|cae|bajista)', 'BAJISTA'),
            ]
            for pat, view in dxy_patterns:
                if re.search(pat, text, re.IGNORECASE | re.DOTALL):
                    return {'view': view, 'rationale': 'Extracted from council text'}

        return None

    # =========================================================================
    # CONVENIENCE METHODS
    # =========================================================================

    def has_structured_data(self) -> bool:
        """Check if any structured blocks were parsed."""
        return len(self._blocks_cache) > 0

    def has_council_text(self) -> bool:
        """Check if any council text is available (even without blocks)."""
        return self._has_council_text()

    def get_all_blocks(self) -> Dict[str, str]:
        """Return all parsed blocks (for debugging)."""
        return dict(self._blocks_cache)

    def get_panel_text(self, agent: str) -> str:
        """Get raw panel text for an agent.

        Args:
            agent: One of 'macro', 'rv', 'rf', 'riesgo', 'geo'.

        Returns:
            Raw text from that agent, or empty string if not found.
        """
        return self._panels.get(agent, '')
