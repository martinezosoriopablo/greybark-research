# -*- coding: utf-8 -*-
"""
Greybark Research - Informe de Antecedentes
=============================================

Formal pre-council background report documenting:
1. Complete data inventory with values, sources, timestamps
2. Missing data fields and their impact
3. Quality flags (stale, errors)
4. Confidence score per agent
5. Exact data snapshot per agent

Output:
- JSON: output/council/antecedentes_YYYY-MM-DD.json
- HTML: output/council/antecedentes_YYYY-MM-DD.html
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from data_manifest import AGENT_MANIFESTS, FieldPriority, get_all_agents
from data_completeness_validator import (
    DataCompletenessValidator, CompletenessResult, AgentCompleteness,
)


OUTPUT_DIR = Path(__file__).parent / "output" / "council"


class AntecedentesReport:
    """Generates a formal background report before the AI Council session."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.validator = DataCompletenessValidator(verbose=False)

    def _print(self, msg: str):
        if self.verbose:
            print(msg)

    def generate(
        self,
        agent_data_map: Dict[str, Dict],
        completeness: CompletenessResult,
        metadata: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Generate the full antecedentes report.

        Args:
            agent_data_map: council_input['agent_data'] — per-agent data dicts
            completeness: result from DataCompletenessValidator.validate()
            metadata: optional pipeline metadata

        Returns:
            Dict with the complete antecedentes structure.
        """
        self._print("[Antecedentes] Generando informe de antecedentes...")

        report = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'verdict': completeness.verdict,
                **(metadata or {}),
            },
            'summary': self._build_summary(completeness),
            'agents': {},
        }

        for agent_name in get_all_agents():
            ac = completeness.agents.get(agent_name)
            if not ac:
                continue

            agent_section = {
                'confidence_score': round(ac.required_coverage * 100, 1),
                'required_coverage': f"{ac.required_present}/{ac.required_total}",
                'important_coverage': f"{ac.important_present}/{ac.important_total}",
                'optional_coverage': f"{ac.optional_present}/{ac.optional_total}",
                'available_data': [],
                'missing_data': [],
            }

            for fs in ac.fields:
                entry = {
                    'field': fs.field.label,
                    'source': fs.field.source,
                    'unit': fs.field.unit,
                    'priority': fs.field.priority.value,
                }
                if fs.status == 'PRESENT':
                    entry['value'] = self._serialize_value(fs.value)
                    entry['status'] = 'available'
                    agent_section['available_data'].append(entry)
                else:
                    entry['status'] = fs.status.lower()
                    entry['impact'] = self._assess_impact(fs.field)
                    agent_section['missing_data'].append(entry)

            report['agents'][agent_name] = agent_section

        self._print(f"[Antecedentes] Informe generado: {completeness.verdict}")
        return report

    def _build_summary(self, completeness: CompletenessResult) -> Dict[str, Any]:
        """Build summary section."""
        total_fields = 0
        total_present = 0
        total_required = 0
        total_req_present = 0

        for ac in completeness.agents.values():
            total_fields += len(ac.fields)
            total_present += len(ac.present_fields)
            total_required += ac.required_total
            total_req_present += ac.required_present

        return {
            'total_fields': total_fields,
            'total_present': total_present,
            'total_coverage_pct': round(total_present / total_fields * 100, 1) if total_fields else 0,
            'required_coverage_pct': round(total_req_present / total_required * 100, 1) if total_required else 0,
            'verdict': completeness.verdict,
            'issues_count': len(completeness.issues),
        }

    def _serialize_value(self, value: Any) -> Any:
        """Serialize a value for JSON, handling complex types."""
        if isinstance(value, (int, float, str, bool)):
            return value
        if isinstance(value, dict):
            # Only include scalar values from dicts to keep JSON manageable
            result = {}
            for k, v in list(value.items())[:20]:
                if isinstance(v, (int, float, str, bool, type(None))):
                    result[k] = v
                elif isinstance(v, dict):
                    result[k] = f"<dict:{len(v)} keys>"
                elif isinstance(v, list):
                    result[k] = f"<list:{len(v)} items>"
            return result
        if isinstance(value, list):
            return f"<list:{len(value)} items>"
        return str(value)[:200]

    def _assess_impact(self, field) -> str:
        """Assess impact of a missing field."""
        if field.priority == FieldPriority.REQUIRED:
            return "CRITICO — agente no puede funcionar correctamente sin este dato"
        elif field.priority == FieldPriority.IMPORTANT:
            return "SIGNIFICATIVO — analisis degradado, posible sesgo por falta de dato"
        return "MENOR — dato complementario, analisis funciona sin el"

    def save_json(self, report: Dict, date_str: str = None) -> str:
        """Save report as JSON."""
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUTPUT_DIR / f"antecedentes_{date_str}.json"

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)

        self._print(f"[Antecedentes] JSON: {path}")
        return str(path)

    def save_html(self, report: Dict, date_str: str = None) -> str:
        """Save report as readable HTML."""
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUTPUT_DIR / f"antecedentes_{date_str}.html"

        html = self._render_html(report, date_str)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)

        self._print(f"[Antecedentes] HTML: {path}")
        return str(path)

    def _render_html(self, report: Dict, date_str: str) -> str:
        """Render the antecedentes report as HTML."""
        summary = report.get('summary', {})
        verdict = summary.get('verdict', 'N/A')
        verdict_color = {
            'GO': '#276749',
            'CAUTION': '#dd6b20',
            'NO_GO': '#c53030',
        }.get(verdict, '#666')

        agent_sections = []
        for agent_name, agent_data in report.get('agents', {}).items():
            rows_available = ""
            for d in agent_data.get('available_data', []):
                val = d.get('value', '')
                if isinstance(val, dict):
                    val_str = json.dumps(val, ensure_ascii=False, default=str)[:200]
                else:
                    val_str = str(val)
                priority_badge = self._priority_badge(d.get('priority', 'optional'))
                rows_available += f"""
                <tr>
                    <td>{d['field']}</td>
                    <td><code>{val_str}</code></td>
                    <td>{d['source']}</td>
                    <td>{d['unit']}</td>
                    <td>{priority_badge}</td>
                </tr>"""

            rows_missing = ""
            for d in agent_data.get('missing_data', []):
                priority_badge = self._priority_badge(d.get('priority', 'optional'))
                rows_missing += f"""
                <tr style="background:#fff5f5;">
                    <td>{d['field']}</td>
                    <td style="color:#c53030;"><strong>{d['status'].upper()}</strong></td>
                    <td>{d['source']}</td>
                    <td>{d['unit']}</td>
                    <td>{priority_badge}</td>
                </tr>"""

            conf = agent_data.get('confidence_score', 0)
            conf_color = '#276749' if conf >= 90 else ('#dd6b20' if conf >= 70 else '#c53030')

            agent_sections.append(f"""
            <div class="agent-section">
                <h2>{agent_name.upper()}
                    <span style="float:right;color:{conf_color};">
                        Confianza: {conf}%
                    </span>
                </h2>
                <p>
                    Required: {agent_data.get('required_coverage', '?')} |
                    Important: {agent_data.get('important_coverage', '?')} |
                    Optional: {agent_data.get('optional_coverage', '?')}
                </p>
                <table>
                    <thead>
                        <tr>
                            <th>Campo</th>
                            <th>Valor</th>
                            <th>Fuente</th>
                            <th>Unidad</th>
                            <th>Prioridad</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_available}
                        {rows_missing}
                    </tbody>
                </table>
            </div>
            """)

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <title>Informe de Antecedentes — {date_str}</title>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; margin: 2rem; color: #1a1a1a; max-width: 1200px; margin: 0 auto; padding: 2rem; }}
        h1 {{ border-bottom: 3px solid #1a1a1a; padding-bottom: 0.5rem; }}
        .verdict {{ display: inline-block; padding: 4px 16px; border-radius: 4px; color: white; font-weight: bold; background: {verdict_color}; }}
        .summary {{ background: #f7f7f7; padding: 1rem; border-radius: 8px; margin: 1rem 0; }}
        .agent-section {{ margin: 2rem 0; border: 1px solid #ddd; border-radius: 8px; padding: 1rem; }}
        .agent-section h2 {{ margin-top: 0; border-bottom: 2px solid #eee; padding-bottom: 0.5rem; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
        th, td {{ text-align: left; padding: 6px 10px; border-bottom: 1px solid #eee; }}
        th {{ background: #f0f0f0; font-weight: 600; }}
        code {{ background: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-size: 0.85em; word-break: break-all; }}
        .badge {{ display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 0.75rem; font-weight: bold; }}
        .badge-required {{ background: #fed7d7; color: #c53030; }}
        .badge-important {{ background: #fefcbf; color: #975a16; }}
        .badge-optional {{ background: #e2e8f0; color: #4a5568; }}
    </style>
</head>
<body>
    <h1>Informe de Antecedentes — Greybark Research</h1>
    <p>Fecha: {date_str} | Generado: {report.get('metadata', {}).get('generated_at', '')}</p>

    <div class="summary">
        <h3>Resumen</h3>
        <p>Veredicto: <span class="verdict">{verdict}</span></p>
        <p>
            Campos totales: {summary.get('total_fields', 0)} |
            Presentes: {summary.get('total_present', 0)} ({summary.get('total_coverage_pct', 0)}%) |
            Required coverage: {summary.get('required_coverage_pct', 0)}% |
            Issues: {summary.get('issues_count', 0)}
        </p>
    </div>

    {''.join(agent_sections)}

    <footer style="margin-top:2rem;padding-top:1rem;border-top:1px solid #ddd;color:#888;font-size:0.8rem;">
        Greybark Research — Pipeline de Integridad de Datos
    </footer>
</body>
</html>"""

    def _priority_badge(self, priority: str) -> str:
        css = {
            'required': 'badge-required',
            'important': 'badge-important',
            'optional': 'badge-optional',
        }.get(priority, 'badge-optional')
        return f'<span class="badge {css}">{priority.upper()}</span>'
