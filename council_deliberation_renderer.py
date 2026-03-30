# -*- coding: utf-8 -*-
"""
Greybark Research - Council Deliberation Report Renderer
=========================================================

Genera un reporte HTML con el acta completa de la deliberación del AI Council.
Muestra las intervenciones de los 8 agentes en orden cronológico:
  Layer 1: 5 panelistas (Macro, RV, RF, Riesgo, Geo) — en paralelo
  Layer 2: CIO Synthesis → Contrarian Challenge → Refinador Final

Usa el council_result JSON que ya se genera en cada pipeline run.
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output" / "reports"


# Agent metadata for display
AGENTS = {
    'macro': {
        'name': 'Economista Jefe',
        'color': '#2b6cb0',
        'layer': 1,
        'description': 'Análisis macroeconómico: crecimiento, inflación, bancos centrales, escenarios',
    },
    'rv': {
        'name': 'Estratega de Renta Variable',
        'color': '#276749',
        'layer': 1,
        'description': 'Valuaciones, earnings, sectores, factores, views regionales',
    },
    'rf': {
        'name': 'Estratega de Renta Fija',
        'color': '#6b46c1',
        'layer': 1,
        'description': 'Duration, crédito, EM debt, Chile soberano/corporativo',
    },
    'riesgo': {
        'name': 'Jefe de Riesgos',
        'color': '#c53030',
        'layer': 1,
        'description': 'VaR, tail risks, correlaciones, hedges, stress testing',
    },
    'geo': {
        'name': 'Analista Geopolítico',
        'color': '#744210',
        'layer': 1,
        'description': 'Riesgos geopolíticos, sanciones, elecciones, commodities',
    },
}

SYNTHESIS_AGENTS = {
    'cio_synthesis': {
        'name': 'Director de Inversiones (CIO)',
        'color': '#1a365d',
        'layer': 2,
        'description': 'Síntesis de las 5 visiones del panel en una recomendación integrada',
    },
    'contrarian_critique': {
        'name': 'Contrarian',
        'color': '#9b2c2c',
        'layer': 2,
        'description': 'Desafía la tesis del CIO, busca supuestos peligrosos y sesgos',
    },
    'final_recommendation': {
        'name': 'Refinador',
        'color': '#2d3748',
        'layer': 2,
        'description': 'Documento final client-facing que integra CIO + ajustes del Contrarian',
    },
}


def _md_to_html(text: str) -> str:
    """Convert basic markdown to HTML."""
    if not text or not isinstance(text, str):
        return ''
    # Headers
    text = re.sub(r'^### (.+)$', r'<h4>\1</h4>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.+)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # Italic
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    # Bloque tags
    text = re.sub(r'\[BLOQUE:\s*(\w+)\]', r'<span class="bloque-tag">[\1]</span>', text)
    # Lists
    text = re.sub(r'^- (.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)
    text = re.sub(r'(<li>.*?</li>\n?)+', r'<ul>\g<0></ul>', text)
    # Horizontal rules
    text = re.sub(r'^---+$', r'<hr>', text, flags=re.MULTILINE)
    # Paragraphs
    paragraphs = text.split('\n\n')
    result = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if p.startswith('<h') or p.startswith('<ul') or p.startswith('<hr'):
            result.append(p)
        else:
            result.append(f'<p>{p}</p>')
    return '\n'.join(result)


def render_deliberation_report(
    council_result: Dict[str, Any],
    branding: Dict[str, str] = None,
    verbose: bool = True,
) -> Optional[str]:
    """
    Genera el reporte HTML de deliberación del AI Council.

    Args:
        council_result: Dict con panel_outputs, cio_synthesis, contrarian_critique, final_recommendation
        branding: Dict con primary_color, accent_color, company_name, font_family
        verbose: Print progress

    Returns:
        Path al archivo HTML generado, o None si falla
    """
    if not council_result:
        if verbose:
            print("[WARN] No council result — skipping deliberation report")
        return None

    branding = branding or {}
    primary_color = branding.get('primary_color', '#1a202c')
    accent_color = branding.get('accent_color', '#dd6b20')
    company_name = branding.get('company_name', 'Greybark Research')
    font_family = branding.get('font_family', 'Segoe UI, Arial, sans-serif')

    meta = council_result.get('metadata', {})
    panel = council_result.get('panel_outputs', {})
    cio = council_result.get('cio_synthesis', '')
    contrarian = council_result.get('contrarian_critique', '')
    final = council_result.get('final_recommendation', '')

    duration_sec = meta.get('duration_seconds', 0)
    duration_min = f"{duration_sec / 60:.1f}" if duration_sec else 'N/D'
    timestamp = meta.get('timestamp', datetime.now().isoformat())
    model_panel = meta.get('model_panel', 'claude-sonnet')
    model_synthesis = meta.get('model_synthesis', 'claude-opus')

    now = datetime.now()
    months_es = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    fecha_display = f"{now.day} {months_es[now.month]} {now.year}"

    if verbose:
        print("=" * 60)
        print("GREYBARK RESEARCH - COUNCIL DELIBERATION REPORT")
        print("=" * 60)

    # Build agent cards
    panel_html = ''
    for agent_id, agent_meta in AGENTS.items():
        text = panel.get(agent_id, '')
        if not text:
            continue
        word_count = len(text.split())
        panel_html += f'''
        <div class="agent-card" style="border-left: 4px solid {agent_meta['color']};">
            <div class="agent-header">
                <div>
                    <span class="agent-name" style="color: {agent_meta['color']};">{agent_meta['name']}</span>
                    <span class="agent-desc">{agent_meta['description']}</span>
                </div>
                <span class="word-count">{word_count} palabras</span>
            </div>
            <div class="agent-content">
                {_md_to_html(text)}
            </div>
        </div>
        '''

    # Build synthesis cards
    synthesis_html = ''
    synthesis_data = [
        ('cio_synthesis', cio),
        ('contrarian_critique', contrarian),
        ('final_recommendation', final),
    ]
    for agent_id, text in synthesis_data:
        if not text:
            continue
        agent_meta = SYNTHESIS_AGENTS[agent_id]
        word_count = len(text.split())
        is_final = agent_id == 'final_recommendation'
        extra_class = ' final-recommendation' if is_final else ''
        synthesis_html += f'''
        <div class="agent-card synthesis-card{extra_class}" style="border-left: 4px solid {agent_meta['color']};">
            <div class="agent-header">
                <div>
                    <span class="agent-name" style="color: {agent_meta['color']};">{agent_meta['name']}</span>
                    <span class="agent-desc">{agent_meta['description']}</span>
                </div>
                <span class="word-count">{word_count} palabras</span>
            </div>
            <div class="agent-content">
                {_md_to_html(text)}
            </div>
        </div>
        '''

    # Council input summary
    input_summary = council_result.get('council_input_summary', {})
    quant_modules = input_summary.get('quantitative_modules', {})
    daily_count = input_summary.get('daily_reports_count', 0)

    input_stats_html = ''
    if quant_modules:
        if isinstance(quant_modules, dict):
            ok_count = sum(1 for v in quant_modules.values() if v == 'OK')
            total = len(quant_modules)
        elif isinstance(quant_modules, list):
            ok_count = sum(1 for v in quant_modules if isinstance(v, dict) and v.get('status') == 'OK')
            total = len(quant_modules)
        else:
            ok_count, total = 0, 0
        input_stats_html = f'''
        <div class="input-stats">
            <div class="stat-item">
                <span class="stat-value">{ok_count}/{total}</span>
                <span class="stat-label">Módulos OK</span>
            </div>
            <div class="stat-item">
                <span class="stat-value">{daily_count}</span>
                <span class="stat-label">Daily Reports</span>
            </div>
            <div class="stat-item">
                <span class="stat-value">{duration_min} min</span>
                <span class="stat-label">Duración</span>
            </div>
            <div class="stat-item">
                <span class="stat-value">{len(panel)}</span>
                <span class="stat-label">Panelistas</span>
            </div>
        </div>
        '''

    # Full HTML
    html = f'''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Acta del Comité de Inversiones — {company_name}</title>
    <style>
        :root {{
            --primary: {primary_color};
            --accent: {accent_color};
            --bg: #f7fafc;
            --surface: #ffffff;
            --text: #1a202c;
            --text-light: #718096;
            --border: #e2e8f0;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: {font_family};
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            font-size: 10.5pt;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
        }}
        /* Header */
        .report-header {{
            background: var(--primary);
            color: white;
            padding: 30px 40px;
            margin: -20px -20px 30px -20px;
        }}
        .report-header h1 {{
            font-size: 22pt;
            font-weight: 700;
            margin-bottom: 5px;
        }}
        .report-header .subtitle {{
            font-size: 11pt;
            opacity: 0.85;
        }}
        .report-header .meta {{
            margin-top: 15px;
            font-size: 9pt;
            opacity: 0.7;
            display: flex;
            gap: 20px;
        }}
        /* Input stats */
        .input-stats {{
            display: flex;
            gap: 15px;
            margin-bottom: 25px;
        }}
        .stat-item {{
            flex: 1;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 15px;
            text-align: center;
        }}
        .stat-value {{
            display: block;
            font-size: 20pt;
            font-weight: 700;
            color: var(--accent);
        }}
        .stat-label {{
            display: block;
            font-size: 8.5pt;
            color: var(--text-light);
            margin-top: 3px;
        }}
        /* Section headers */
        .layer-header {{
            background: var(--primary);
            color: white;
            padding: 12px 20px;
            border-radius: 6px;
            margin: 30px 0 15px 0;
            font-size: 13pt;
            font-weight: 600;
        }}
        .layer-header .layer-desc {{
            font-size: 9pt;
            opacity: 0.8;
            font-weight: 400;
            margin-top: 3px;
        }}
        /* Agent cards */
        .agent-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            margin-bottom: 15px;
            overflow: hidden;
            page-break-inside: avoid;
        }}
        .agent-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 16px;
            background: #f8f9fa;
            border-bottom: 1px solid var(--border);
        }}
        .agent-icon {{
            font-size: 20pt;
        }}
        .agent-name {{
            display: block;
            font-weight: 700;
            font-size: 11pt;
        }}
        .agent-desc {{
            display: block;
            font-size: 8.5pt;
            color: var(--text-light);
        }}
        .word-count {{
            margin-left: auto;
            font-size: 8pt;
            color: var(--text-light);
            white-space: nowrap;
        }}
        .agent-content {{
            padding: 16px 20px;
            font-size: 10pt;
            line-height: 1.65;
        }}
        .agent-content h2 {{
            font-size: 12pt;
            color: var(--primary);
            margin: 15px 0 8px 0;
            border-bottom: 1px solid var(--border);
            padding-bottom: 4px;
        }}
        .agent-content h3 {{
            font-size: 11pt;
            color: var(--primary);
            margin: 12px 0 6px 0;
        }}
        .agent-content h4 {{
            font-size: 10pt;
            color: var(--text);
            margin: 10px 0 5px 0;
        }}
        .agent-content p {{
            margin-bottom: 8px;
        }}
        .agent-content ul {{
            margin: 5px 0 10px 20px;
        }}
        .agent-content li {{
            margin-bottom: 3px;
        }}
        .agent-content hr {{
            margin: 12px 0;
            border: none;
            border-top: 1px solid var(--border);
        }}
        /* Bloque tags */
        .bloque-tag {{
            background: var(--accent);
            color: white;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 8pt;
            font-weight: 700;
            font-family: monospace;
        }}
        /* Synthesis cards */
        .synthesis-card {{
            border-width: 4px;
        }}
        .final-recommendation {{
            border-color: var(--accent) !important;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}
        .final-recommendation .agent-header {{
            background: #fffaf0;
        }}
        /* Footer */
        .report-footer {{
            margin-top: 30px;
            padding: 15px 0;
            border-top: 2px solid var(--border);
            font-size: 8pt;
            color: var(--text-light);
            text-align: center;
        }}
        /* Print */
        @media print {{
            body {{ font-size: 9pt; }}
            .container {{ max-width: 100%; padding: 0; }}
            .report-header {{ margin: 0 0 20px 0; }}
            .agent-card {{ page-break-inside: avoid; }}
        }}
    </style>
</head>
<body>
<div class="container">
    <div class="report-header">
        <h1>Acta del Comité de Inversiones</h1>
        <div class="subtitle">{company_name} — {fecha_display}</div>
        <div class="meta">
            <span>Panel: {model_panel}</span>
            <span>Síntesis: {model_synthesis}</span>
            <span>Duración: {duration_min} min</span>
            <span>Sesión: {timestamp[:16]}</span>
        </div>
    </div>

    {input_stats_html}

    <div class="layer-header">
        Capa 1 — Panel de Especialistas
        <div class="layer-desc">5 analistas deliberan en paralelo, cada uno con datos filtrados por su expertise</div>
    </div>

    {panel_html}

    <div class="layer-header">
        Capa 2 — Síntesis y Desafío
        <div class="layer-desc">CIO integra → Contrarian desafía → Refinador produce documento final</div>
    </div>

    {synthesis_html}

    <div class="report-footer">
        {company_name} — Acta generada automáticamente por AI Council<br>
        Este documento es confidencial y para uso interno del comité de inversiones.
    </div>
</div>
</body>
</html>'''

    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = now.strftime('%Y-%m-%d')
    filename = f"council_deliberation_{date_str}.html"
    filepath = OUTPUT_DIR / filename
    filepath.write_text(html, encoding='utf-8')

    if verbose:
        print(f"[OK] Acta generada: {filepath}")
        print(f"     Panel: {len(panel)} agentes, CIO: {len(cio)} chars, "
              f"Contrarian: {len(contrarian)} chars, Final: {len(final)} chars")

    return str(filepath)


def render_from_file(council_json_path: str, branding: Dict = None, verbose: bool = True) -> Optional[str]:
    """Render deliberation report from a saved council result JSON file."""
    with open(council_json_path, encoding='utf-8') as f:
        council_result = json.load(f)
    return render_deliberation_report(council_result, branding=branding, verbose=verbose)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Render Council Deliberation Report')
    parser.add_argument('council_json', nargs='?', help='Path to council_result JSON')
    args = parser.parse_args()

    if args.council_json:
        path = args.council_json
    else:
        # Find latest council result
        council_dir = BASE_DIR / "output" / "council"
        files = sorted(council_dir.glob("council_result_*.json"), reverse=True)
        if not files:
            print("[ERR] No council results found")
            sys.exit(1)
        path = str(files[0])
        print(f"Using latest: {path}")

    result = render_from_file(path)
    if result:
        print(f"\nDone: {result}")
