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
        """Render the antecedentes report as professional HTML."""
        summary = report.get('summary', {})
        verdict = summary.get('verdict', 'N/A')
        verdict_color = {'GO': '#276749', 'CAUTION': '#dd6b20', 'NO_GO': '#c53030'}.get(verdict, '#666')
        verdict_bg = {'GO': '#f0fff4', 'CAUTION': '#fffff0', 'NO_GO': '#fff5f5'}.get(verdict, '#f7f7f7')
        verdict_icon = {'GO': '&#10003;', 'CAUTION': '&#9888;', 'NO_GO': '&#10007;'}.get(verdict, '?')

        total_f = summary.get('total_fields', 0)
        total_p = summary.get('total_present', 0)
        cov_pct = summary.get('total_coverage_pct', 0)
        req_pct = summary.get('required_coverage_pct', 0)
        issues = summary.get('issues_count', 0)

        agent_sections = []
        agent_labels = {
            'macro': 'Macro & Geopolítica',
            'rv': 'Renta Variable',
            'rf': 'Renta Fija',
            'riesgo': 'Riesgo',
            'geopolitica': 'Geopolítica',
        }

        for agent_name, agent_data in report.get('agents', {}).items():
            conf = agent_data.get('confidence_score', 0)
            conf_color = '#276749' if conf >= 90 else ('#dd6b20' if conf >= 70 else '#c53030')
            conf_bg = '#f0fff4' if conf >= 90 else ('#fffff0' if conf >= 70 else '#fff5f5')
            conf_icon = '&#10003;' if conf >= 90 else ('&#9888;' if conf >= 70 else '&#10007;')

            n_avail = len(agent_data.get('available_data', []))
            n_miss = len(agent_data.get('missing_data', []))

            # --- Available data table ---
            rows_available = ""
            for d in agent_data.get('available_data', []):
                val = d.get('value', '')
                if isinstance(val, dict):
                    val_str = json.dumps(val, ensure_ascii=False, default=str)[:150]
                else:
                    val_str = str(val)
                    if len(val_str) > 100:
                        val_str = val_str[:100] + '...'
                rows_available += (
                    f'<tr>'
                    f'<td>{d["field"]}</td>'
                    f'<td><code>{val_str}</code></td>'
                    f'<td>{self._source_badge(d["source"])}</td>'
                    f'<td class="center">{d["unit"]}</td>'
                    f'<td class="center">{self._priority_badge(d.get("priority", "optional"))}</td>'
                    f'</tr>'
                )

            # --- Missing data table ---
            rows_missing = ""
            for d in agent_data.get('missing_data', []):
                impact = d.get('impact', '')
                impact_badge = self._impact_badge(impact)
                rows_missing += (
                    f'<tr>'
                    f'<td>{d["field"]}</td>'
                    f'<td class="center"><span class="status-missing">{d["status"].upper()}</span></td>'
                    f'<td>{self._source_badge(d["source"])}</td>'
                    f'<td class="center">{self._priority_badge(d.get("priority", "optional"))}</td>'
                    f'<td>{impact_badge}</td>'
                    f'</tr>'
                )

            # Missing section (open by default)
            missing_html = ""
            if rows_missing:
                missing_html = f"""
                <details open class="data-block missing-block">
                    <summary>Datos Faltantes ({n_miss})</summary>
                    <table class="data-table missing-table">
                        <thead><tr>
                            <th>Campo</th><th class="center">Status</th>
                            <th>Fuente</th><th class="center">Prioridad</th><th>Impacto</th>
                        </tr></thead>
                        <tbody>{rows_missing}</tbody>
                    </table>
                </details>"""

            # Available section (collapsed by default)
            available_html = ""
            if rows_available:
                available_html = f"""
                <details class="data-block">
                    <summary>Datos Disponibles ({n_avail})</summary>
                    <table class="data-table">
                        <thead><tr>
                            <th>Campo</th><th>Valor</th>
                            <th>Fuente</th><th class="center">Unidad</th><th class="center">Prioridad</th>
                        </tr></thead>
                        <tbody>{rows_available}</tbody>
                    </table>
                </details>"""

            label = agent_labels.get(agent_name, agent_name.upper())

            agent_sections.append(f"""
            <div class="agent-section">
                <div class="agent-header">
                    <div class="agent-title">
                        <h2>{label}</h2>
                        <div class="coverage-pills">
                            <span class="pill pill-req">REQ {agent_data.get('required_coverage', '?')}</span>
                            <span class="pill pill-imp">IMP {agent_data.get('important_coverage', '?')}</span>
                            <span class="pill pill-opt">OPT {agent_data.get('optional_coverage', '?')}</span>
                        </div>
                    </div>
                    <div class="confidence-display" style="color:{conf_color};">
                        <span class="conf-icon" style="background:{conf_bg};color:{conf_color};">{conf_icon}</span>
                        {conf}%
                    </div>
                </div>
                <div class="progress-bar-container">
                    <div class="progress-bar" style="width:{min(conf, 100)}%;background:{conf_color};"></div>
                </div>
                {missing_html}
                {available_html}
            </div>""")

        generated_at = report.get('metadata', {}).get('generated_at', '')

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Informe de Antecedentes — {date_str}</title>
    <style>
        :root {{
            --primary: #1a1a1a;
            --accent: #dd6b20;
            --positive: #276749;
            --negative: #c53030;
            --caution: #dd6b20;
            --bg-light: #f7f7f7;
            --bg-page: #fafafa;
            --border: #e0e0e0;
            --text: #1a1a1a;
            --text-mid: #4a4a4a;
            --text-light: #717171;
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
            font-size: 10pt;
            line-height: 1.5;
            color: var(--text);
            background: var(--bg-page);
        }}

        .container {{
            max-width: 1100px;
            margin: 0 auto;
            padding: 30px 40px;
            background: white;
            min-height: 100vh;
        }}

        /* Header */
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            border-bottom: 3px solid var(--primary);
            padding-bottom: 15px;
            margin-bottom: 25px;
        }}

        .header h1 {{
            font-size: 20pt;
            font-weight: 900;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            color: var(--primary);
        }}

        .header .subtitle {{
            font-size: 11pt;
            color: var(--accent);
            font-weight: 500;
            margin-top: 2px;
        }}

        .header-right {{
            text-align: right;
            font-size: 9pt;
            color: var(--text-mid);
        }}

        .header-right .date {{
            font-size: 12pt;
            font-weight: 600;
            color: var(--primary);
        }}

        /* Verdict Badge */
        .verdict-badge {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 20px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 13pt;
            letter-spacing: 1px;
        }}

        /* Summary Cards */
        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin: 25px 0;
        }}

        .card {{
            background: var(--bg-light);
            border-radius: 8px;
            padding: 16px 20px;
            border-left: 4px solid var(--border);
        }}

        .card-icon {{
            font-size: 18pt;
            margin-bottom: 4px;
        }}

        .card-value {{
            font-size: 20pt;
            font-weight: 700;
            color: var(--primary);
            line-height: 1.2;
        }}

        .card-label {{
            font-size: 8.5pt;
            color: var(--text-light);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: 2px;
        }}

        .card-accent {{ border-left-color: var(--accent); }}
        .card-positive {{ border-left-color: var(--positive); }}
        .card-negative {{ border-left-color: var(--negative); }}
        .card-primary {{ border-left-color: var(--primary); }}

        /* Agent Sections */
        .agent-section {{
            margin: 24px 0;
            border: 1px solid var(--border);
            border-radius: 10px;
            overflow: hidden;
        }}

        .agent-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 20px 12px;
            background: var(--bg-light);
        }}

        .agent-title h2 {{
            font-size: 13pt;
            font-weight: 700;
            color: var(--primary);
            margin-bottom: 6px;
        }}

        .coverage-pills {{
            display: flex;
            gap: 8px;
        }}

        .pill {{
            display: inline-block;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 8pt;
            font-weight: 600;
            letter-spacing: 0.3px;
        }}

        .pill-req {{ background: #fed7d7; color: #9b2c2c; }}
        .pill-imp {{ background: #fefcbf; color: #975a16; }}
        .pill-opt {{ background: #e2e8f0; color: #4a5568; }}

        .confidence-display {{
            font-size: 18pt;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .conf-icon {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 32px;
            height: 32px;
            border-radius: 50%;
            font-size: 14pt;
        }}

        /* Progress Bar */
        .progress-bar-container {{
            height: 4px;
            background: #e8e8e8;
        }}

        .progress-bar {{
            height: 100%;
            transition: width 0.3s;
            border-radius: 0 2px 2px 0;
        }}

        /* Data Blocks */
        .data-block {{
            padding: 0 20px;
            margin: 12px 0;
        }}

        .data-block summary {{
            cursor: pointer;
            font-weight: 600;
            font-size: 10pt;
            color: var(--text-mid);
            padding: 8px 0;
            border-bottom: 1px solid var(--border);
            list-style: none;
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        .data-block summary::before {{
            content: '\\25B6';
            font-size: 8pt;
            transition: transform 0.2s;
        }}

        .data-block[open] summary::before {{
            transform: rotate(90deg);
        }}

        .missing-block summary {{
            color: var(--negative);
        }}

        /* Tables */
        .data-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 9pt;
            margin: 8px 0 16px;
        }}

        .data-table th {{
            background: var(--primary);
            color: white;
            padding: 8px 10px;
            text-align: left;
            font-weight: 600;
            font-size: 8.5pt;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }}

        .data-table th.center {{ text-align: center; }}

        .data-table td {{
            padding: 6px 10px;
            border-bottom: 1px solid #f0f0f0;
            vertical-align: top;
        }}

        .data-table td.center {{ text-align: center; }}

        .data-table tbody tr:nth-child(even) {{
            background: #fafafa;
        }}

        .data-table tbody tr:hover {{
            background: #f0f4f8;
        }}

        .missing-table tbody tr {{
            background: #fff8f8;
        }}

        .missing-table tbody tr:nth-child(even) {{
            background: #fff0f0;
        }}

        .missing-table tbody tr:hover {{
            background: #ffe8e8;
        }}

        code {{
            background: #f0f0f0;
            padding: 1px 6px;
            border-radius: 3px;
            font-size: 8.5pt;
            word-break: break-all;
            font-family: 'Cascadia Code', 'Consolas', monospace;
        }}

        /* Badges */
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 7.5pt;
            font-weight: 700;
            letter-spacing: 0.3px;
            text-transform: uppercase;
        }}

        .badge-required {{ background: #fed7d7; color: #9b2c2c; }}
        .badge-important {{ background: #fefcbf; color: #975a16; }}
        .badge-optional {{ background: #e2e8f0; color: #4a5568; }}

        .source-badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 7.5pt;
            font-weight: 600;
            letter-spacing: 0.3px;
        }}

        .src-bcch {{ background: #ebf4ff; color: #2b6cb0; }}
        .src-fred {{ background: #f0fff4; color: #276749; }}
        .src-yfinance {{ background: #faf5ff; color: #6b46c1; }}
        .src-bloomberg {{ background: #fffff0; color: #975a16; }}
        .src-bea {{ background: #fff5f5; color: #c53030; }}
        .src-akshare {{ background: #fefcbf; color: #744210; }}
        .src-imf {{ background: #e6fffa; color: #285e61; }}
        .src-ecb {{ background: #ebf4ff; color: #2a4365; }}
        .src-other {{ background: #f0f0f0; color: #4a5568; }}

        .status-missing {{
            display: inline-block;
            padding: 2px 10px;
            border-radius: 3px;
            font-size: 7.5pt;
            font-weight: 700;
            background: #fed7d7;
            color: #9b2c2c;
        }}

        .impact-badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 7.5pt;
            font-weight: 600;
        }}

        .impact-critico {{ background: #fed7d7; color: #9b2c2c; }}
        .impact-significativo {{ background: #fefcbf; color: #975a16; }}
        .impact-menor {{ background: #e2e8f0; color: #4a5568; }}

        /* Footer */
        .footer {{
            margin-top: 40px;
            padding-top: 16px;
            border-top: 2px solid var(--primary);
            display: flex;
            justify-content: space-between;
            color: var(--text-light);
            font-size: 8pt;
        }}

        /* Print */
        @media print {{
            body {{ background: white; }}
            .container {{ padding: 0; }}
            .agent-section {{ page-break-inside: avoid; }}
            details {{ open: true; }}
            .data-block summary::before {{ display: none; }}
        }}

        @media (max-width: 768px) {{
            .summary-cards {{ grid-template-columns: repeat(2, 1fr); }}
            .header {{ flex-direction: column; gap: 10px; }}
            .header-right {{ text-align: left; }}
            .container {{ padding: 16px; }}
        }}
    </style>
</head>
<body>
<div class="container">

    <!-- Header -->
    <div class="header">
        <div>
            <h1>Informe de Antecedentes</h1>
            <div class="subtitle">Pre-Council Data Integrity Report</div>
        </div>
        <div class="header-right">
            <div class="date">{date_str}</div>
            <div>Pipeline de Integridad de Datos</div>
        </div>
    </div>

    <!-- Verdict -->
    <div style="text-align:center;margin:20px 0;">
        <span class="verdict-badge" style="background:{verdict_bg};color:{verdict_color};border:2px solid {verdict_color};">
            {verdict_icon} {verdict}
        </span>
    </div>

    <!-- Summary Cards -->
    <div class="summary-cards">
        <div class="card card-primary">
            <div class="card-icon">&#128202;</div>
            <div class="card-value">{total_f}</div>
            <div class="card-label">Campos Totales</div>
        </div>
        <div class="card card-positive">
            <div class="card-icon">&#10003;</div>
            <div class="card-value">{total_p}</div>
            <div class="card-label">Presentes ({cov_pct}%)</div>
        </div>
        <div class="card card-accent">
            <div class="card-icon">&#9733;</div>
            <div class="card-value">{req_pct}%</div>
            <div class="card-label">Cobertura Required</div>
        </div>
        <div class="card {'card-negative' if issues > 5 else 'card-accent'}">
            <div class="card-icon">&#9888;</div>
            <div class="card-value">{issues}</div>
            <div class="card-label">Issues Detectados</div>
        </div>
    </div>

    <!-- Agent Sections -->
    {''.join(agent_sections)}

    <!-- Footer -->
    <div class="footer">
        <span>Greybark Research &mdash; Pipeline de Integridad de Datos</span>
        <span>Generado: {generated_at}</span>
    </div>

</div>
</body>
</html>"""

    def _priority_badge(self, priority: str) -> str:
        css = {
            'required': 'badge-required',
            'important': 'badge-important',
            'optional': 'badge-optional',
        }.get(priority, 'badge-optional')
        return f'<span class="badge {css}">{priority.upper()}</span>'

    def _source_badge(self, source: str) -> str:
        """Render a colored badge for the data source."""
        s = source.lower() if source else ''
        if 'bcch' in s:
            css, label = 'src-bcch', 'BCCh'
        elif 'fred' in s:
            css, label = 'src-fred', 'FRED'
        elif 'yfinance' in s:
            css, label = 'src-yfinance', 'yfinance'
        elif 'bloomberg' in s or 'bbg' in s:
            css, label = 'src-bloomberg', 'Bloomberg'
        elif 'bea' in s:
            css, label = 'src-bea', 'BEA'
        elif 'akshare' in s or 'nbs' in s:
            css, label = 'src-akshare', 'NBS'
        elif 'imf' in s:
            css, label = 'src-imf', 'IMF'
        elif 'ecb' in s:
            css, label = 'src-ecb', 'ECB'
        else:
            css, label = 'src-other', source[:20] if source else '?'
        return f'<span class="source-badge {css}">{label}</span>'

    def _impact_badge(self, impact: str) -> str:
        """Render impact badge from impact string."""
        if not impact:
            return ''
        if 'CRITICO' in impact.upper():
            return f'<span class="impact-badge impact-critico">CRITICO</span>'
        elif 'SIGNIFICATIVO' in impact.upper():
            return f'<span class="impact-badge impact-significativo">SIGNIFICATIVO</span>'
        return f'<span class="impact-badge impact-menor">MENOR</span>'
