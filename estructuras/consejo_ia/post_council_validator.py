# -*- coding: utf-8 -*-
"""
Greybark Research - Post-Council Validator
============================================

After the 8 agents run, extracts ALL numbers from their outputs and
cross-references them against the data they actually received.

Classifications:
- VERIFIED: matches a known API data point (within tolerance)
- JUDGMENT: agent's own estimate (probabilities, horizons, etc.)
- DISCREPANCY: labelled near a known indicator but value differs
- UNMATCHED: no match found, not clearly a judgment → possible fabrication
"""

import re
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

# Reuse the anti-fabrication machinery from narrative_engine
from narrative_engine import (
    _extract_numbers, _find_label_number_pairs,
    _is_significant_discrepancy, _LABEL_PATTERNS,
)
from data_manifest import AGENT_MANIFESTS, FieldPriority
from data_completeness_validator import DataCompletenessValidator


OUTPUT_DIR = Path(__file__).parent / "output" / "council"

# Patterns that identify "judgment" numbers — agent estimates, not data
_JUDGMENT_PATTERNS = [
    re.compile(r'probabil\w+\s+(?:de\s+)?(?:~?\d)', re.IGNORECASE),
    re.compile(r'estimamos?\s', re.IGNORECASE),
    re.compile(r'esperamos?\s', re.IGNORECASE),
    re.compile(r'proyectamos?\s', re.IGNORECASE),
    re.compile(r'(?:prob|probabilidad)\s*(?:=|:)\s*\d', re.IGNORECASE),
    re.compile(r'(?:horizonte|plazo)\s+(?:de\s+)?\d', re.IGNORECASE),
    re.compile(r'rango\s+(?:de\s+)?\d', re.IGNORECASE),
    re.compile(r'(?:target|objetivo)\s*(?:de\s*)?\d', re.IGNORECASE),
    re.compile(r'\d+\s*%\s*(?:de\s+)?probabilidad', re.IGNORECASE),
    re.compile(r'escenario\s+\w+.*?\d+\s*%', re.IGNORECASE),
]


class PostCouncilValidator:
    """Validates agent outputs against their input data."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.completeness_validator = DataCompletenessValidator(verbose=False)

    def _print(self, msg: str):
        if self.verbose:
            print(msg)

    def _build_verified_data(self, agent: str, agent_data: Dict) -> Dict[str, float]:
        """Extract all scalar numeric values from agent data into a flat dict.

        Maps manifest labels to their values for cross-referencing.
        Also builds a key→value map matching the narrative_engine label patterns.
        """
        vd: Dict[str, float] = {}

        ac = self.completeness_validator.validate_agent(agent, agent_data)

        for fs in ac.present_fields:
            if isinstance(fs.value, (int, float)):
                # Map to standard keys used by _LABEL_PATTERNS
                key = self._manifest_path_to_key(fs.field.path, fs.field.label)
                if key:
                    vd[key] = float(fs.value)

        # Also extract from nested dicts for broader coverage
        self._extract_nested_numerics(agent_data, vd)

        return vd

    def _manifest_path_to_key(self, path: str, label: str) -> Optional[str]:
        """Map a manifest path/label to a narrative_engine verified_data key."""
        mapping = {
            'macro_usa.gdp': 'us_gdp',
            'macro_usa.unemployment': 'us_unemployment',
            'macro_usa.fed_funds': 'fed_rate',
            'inflation.cpi_core_yoy': 'core_cpi',
            'inflation.cpi_all_yoy': 'headline_cpi',
            'inflation.breakeven_5y': 'breakeven_5y',
            'inflation.breakeven_10y': 'breakeven_10y',
            'inflation.real_rate_10y': 'tips_10y',
            'chile.tpm': 'tpm',
            'chile.ipc_yoy': 'chile_ipc',
            'chile.imacec': 'chile_imacec',
            'chile.pib_yoy': 'chile_gdp',
            'risk.vix': 'vix',
            'breadth.pct_above_50ma': 'breadth_50ma',
            'breadth.cyclical_defensive_spread': 'cyclical_defensive',
            'equity_data.valuations.us.pe_trailing': 'sp500_pe',
            'equity_data.valuations.europe.pe_trailing': 'stoxx600_pe',
            'equity_data.valuations.em.pe_trailing': 'msci_em_pe',
            'equity_data.valuations.chile.pe_trailing': 'ipsa_pe',
            'equity_data.valuations.us.pe_fwd': 'sp500_fwd_pe',
        }
        return mapping.get(path)

    def _extract_nested_numerics(self, data: Dict, vd: Dict[str, float], prefix: str = ""):
        """Recursively extract numeric values from nested dicts."""
        if not isinstance(data, dict):
            return
        for k, v in data.items():
            if k == 'error':
                continue
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                # Only store if we don't already have it
                if full_key not in vd:
                    vd[full_key] = float(v)
            elif isinstance(v, dict):
                self._extract_nested_numerics(v, vd, full_key)

    def validate_agent_output(
        self,
        agent: str,
        output_text: str,
        agent_data: Dict,
    ) -> Dict[str, Any]:
        """Validate a single agent's output against their input data.

        Returns dict with:
        - total_numbers: count of numbers found
        - classifications: list of {value, classification, context, ...}
        - summary: counts per classification type
        """
        # Strip HTML for analysis
        clean = re.sub(r'<[^>]+>', ' ', output_text)

        numbers = _extract_numbers(clean)
        verified_data = self._build_verified_data(agent, agent_data)

        # Match labels to numbers using narrative_engine machinery
        pairs = _find_label_number_pairs(clean, numbers, verified_data)
        paired_indices = {id(p[0]) for p in pairs}

        classifications = []

        # Process paired numbers (have label context)
        for num_info, key, verified_val in pairs:
            narrative_val = num_info['value']
            unit = num_info['unit']

            ctx_start = max(0, num_info['start'] - 40)
            ctx_end = min(len(clean), num_info['end'] + 40)
            context = clean[ctx_start:ctx_end].strip()

            if _is_significant_discrepancy(narrative_val, verified_val, unit):
                classifications.append({
                    'value': narrative_val,
                    'unit': unit,
                    'classification': 'DISCREPANCY',
                    'verified_key': key,
                    'verified_value': verified_val,
                    'context': context,
                })
            else:
                classifications.append({
                    'value': narrative_val,
                    'unit': unit,
                    'classification': 'VERIFIED',
                    'verified_key': key,
                    'verified_value': verified_val,
                    'context': context,
                })

        # Process unpaired numbers
        for num_info in numbers:
            if id(num_info) in paired_indices:
                continue

            ctx_start = max(0, num_info['start'] - 40)
            ctx_end = min(len(clean), num_info['end'] + 40)
            context = clean[ctx_start:ctx_end].strip()

            # Check if it's a judgment/estimate
            if self._is_judgment(context, num_info):
                classifications.append({
                    'value': num_info['value'],
                    'unit': num_info['unit'],
                    'classification': 'JUDGMENT',
                    'context': context,
                })
            else:
                # Try to find a close match in all known values
                close_match = self._find_close_match(num_info['value'], verified_data)
                if close_match:
                    classifications.append({
                        'value': num_info['value'],
                        'unit': num_info['unit'],
                        'classification': 'CLOSE',
                        'possible_key': close_match[0],
                        'possible_value': close_match[1],
                        'context': context,
                    })
                else:
                    classifications.append({
                        'value': num_info['value'],
                        'unit': num_info['unit'],
                        'classification': 'UNMATCHED',
                        'context': context,
                    })

        # Build summary
        summary = {}
        for c in classifications:
            cls = c['classification']
            summary[cls] = summary.get(cls, 0) + 1

        return {
            'agent': agent,
            'total_numbers': len(numbers),
            'classifications': classifications,
            'summary': summary,
        }

    def _is_judgment(self, context: str, num_info: dict) -> bool:
        """Check if a number is an agent judgment/estimate based on context."""
        for pattern in _JUDGMENT_PATTERNS:
            if pattern.search(context):
                return True
        # Percentages in certain ranges that look like probability estimates
        if num_info['unit'] == '%' and 10 <= num_info['value'] <= 90:
            # Check if it looks like a probability assignment
            if re.search(r'(?:prob|escenario|base|alternativo|riesgo)', context, re.IGNORECASE):
                return True
        return False

    def _find_close_match(
        self, value: float, verified: Dict[str, float], tolerance: float = 0.10
    ) -> Optional[Tuple[str, float]]:
        """Find a close match for a value in the verified data."""
        for key, vval in verified.items():
            if vval == 0:
                continue
            if abs(value - vval) / abs(vval) < tolerance:
                return (key, vval)
        return None

    def validate_all(
        self,
        council_result: Dict[str, Any],
        council_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Validate all agent outputs from a council session.

        Args:
            council_result: full council result dict
            council_input: full council input dict (with agent_data)

        Returns:
            ValidationReport dict with per-agent and aggregate results.
        """
        self._print("\n[PostCouncilValidator] Validando outputs de agentes...")

        agent_data_map = council_input.get('agent_data', {})
        panel_outputs = council_result.get('panel_outputs', {})

        # Validate panel agents
        results = {}
        total_flags = 0

        for agent in ['macro', 'rv', 'rf', 'riesgo', 'geo']:
            output = panel_outputs.get(agent, '')
            agent_data = agent_data_map.get(agent, {})

            if not output:
                continue

            result = self.validate_agent_output(agent, output, agent_data)
            results[agent] = result

            n_disc = result['summary'].get('DISCREPANCY', 0)
            n_unm = result['summary'].get('UNMATCHED', 0)
            n_ver = result['summary'].get('VERIFIED', 0)
            n_jdg = result['summary'].get('JUDGMENT', 0)
            total_flags += n_disc + n_unm

            self._print(
                f"  {agent.upper():>8}: {result['total_numbers']} nums | "
                f"VERIFIED={n_ver} JUDGMENT={n_jdg} DISCREPANCY={n_disc} UNMATCHED={n_unm}"
            )

        # Also validate synthesis agents against combined data
        for synth_agent in ['cio', 'contrarian', 'refinador']:
            output = ''
            if synth_agent == 'cio':
                output = council_result.get('cio_synthesis', '')
            elif synth_agent == 'contrarian':
                output = council_result.get('contrarian_critique', '')
            elif synth_agent == 'refinador':
                output = council_result.get('final_recommendation', '')

            if not output:
                continue

            # Synthesis agents see all data — combine all agent data
            combined = {}
            for a_data in agent_data_map.values():
                if isinstance(a_data, dict):
                    combined.update(a_data)

            result = self.validate_agent_output(synth_agent, output, combined)
            results[synth_agent] = result

            n_disc = result['summary'].get('DISCREPANCY', 0)
            n_unm = result['summary'].get('UNMATCHED', 0)
            total_flags += n_disc + n_unm

            self._print(
                f"  {synth_agent.upper():>8}: {result['total_numbers']} nums | "
                f"DISC={n_disc} UNM={n_unm}"
            )

        # Aggregate
        all_flags = []
        for agent_name, r in results.items():
            for c in r['classifications']:
                if c['classification'] in ('DISCREPANCY', 'UNMATCHED'):
                    all_flags.append({
                        'agent': agent_name,
                        **c,
                    })

        report = {
            'timestamp': datetime.now().isoformat(),
            'agents': results,
            'total_flags': total_flags,
            'flags': all_flags,
            'verdict': 'CLEAN' if total_flags == 0 else (
                'MINOR' if total_flags <= 5 else 'SIGNIFICANT'
            ),
        }

        self._print(f"  Total flags: {total_flags} | Verdict: {report['verdict']}")
        return report

    def save(self, report: Dict, date_str: str = None) -> str:
        """Save validation report to JSON."""
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUTPUT_DIR / f"validation_{date_str}.json"

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)

        self._print(f"[PostCouncilValidator] Saved: {path}")
        return str(path)

    def format_report(self, report: Dict) -> str:
        """Format validation report for console output."""
        lines = [
            "",
            "=" * 60,
            "POST-COUNCIL VALIDATION REPORT",
            "=" * 60,
            f"  Verdict: [{report.get('verdict', '?')}]",
            f"  Total flags: {report.get('total_flags', 0)}",
            "",
        ]

        for agent_name, r in report.get('agents', {}).items():
            s = r.get('summary', {})
            lines.append(
                f"  {agent_name.upper():>12}: "
                f"V={s.get('VERIFIED', 0)} "
                f"J={s.get('JUDGMENT', 0)} "
                f"C={s.get('CLOSE', 0)} "
                f"D={s.get('DISCREPANCY', 0)} "
                f"U={s.get('UNMATCHED', 0)}"
            )

        flags = report.get('flags', [])
        if flags:
            lines.append(f"\n  --- FLAGGED NUMBERS ({len(flags)}) ---")
            for f in flags[:20]:  # Show first 20
                cls = f.get('classification', '?')
                ctx = f.get('context', '')[:60]
                val = f.get('value', '?')
                agent = f.get('agent', '?')
                ver_val = f.get('verified_value', '')
                ver_str = f" (verified: {ver_val})" if ver_val else ""
                lines.append(f"    [{cls}] {agent}: {val}{ver_str} — \"{ctx}\"")

        lines.append("=" * 60)
        return "\n".join(lines)
