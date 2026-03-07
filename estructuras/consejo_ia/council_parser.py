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
        """Extract scenario probabilities.

        Returns:
            {scenario_key: {'prob': float, 'name': str}} or None.
            prob is 0.0-1.0.
        """
        block = self._get_block('ESCENARIOS')
        if not block:
            return None

        scenarios = {}
        # Pattern: - Base/Alternativo: {name}, probabilidad {X}%
        pattern = (
            r'-\s*(?:Base|Alternativo[_\s]*\d*|Upside|Downside)'
            r'[:\s]*([^,]+),\s*probabilidad\s+(\d+)%'
        )
        for match in re.finditer(pattern, block, re.IGNORECASE):
            name = match.group(1).strip()
            prob = float(match.group(2)) / 100.0
            # Normalize scenario name
            key = name.lower().replace(' ', '_')
            scenarios[key] = {'prob': prob, 'name': name}

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
    # CONVENIENCE METHODS
    # =========================================================================

    def has_structured_data(self) -> bool:
        """Check if any structured blocks were parsed."""
        return len(self._blocks_cache) > 0

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
