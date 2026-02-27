# -*- coding: utf-8 -*-
"""
Greybark Research - Council Minutes Renderer
=============================================

Renderiza el JSON del AI Council como minuta HTML profesional.

Uso:
    python council_minutes_renderer.py [council_result.json]
    # Sin argumento: usa el más reciente
"""

import re
import sys
import json
from pathlib import Path
from datetime import datetime

MESES_ES = {
    1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
    5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
    9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre',
}

AGENT_META = {
    'macro': {
        'name': 'IAS Macro',
        'role': 'Macroeconomic Strategist',
        'icon': '&#127758;',  # globe
        'color': '#2b6cb0',
    },
    'rv': {
        'name': 'IAS Renta Variable',
        'role': 'Equity Strategist',
        'icon': '&#128200;',  # chart up
        'color': '#276749',
    },
    'rf': {
        'name': 'IAS Renta Fija',
        'role': 'Fixed Income Strategist',
        'icon': '&#128201;',  # chart down
        'color': '#744210',
    },
    'riesgo': {
        'name': 'IAS Riesgo',
        'role': 'Chief Risk Officer',
        'icon': '&#9888;',  # warning
        'color': '#c53030',
    },
    'geo': {
        'name': 'IAS Geopol&iacute;tica',
        'role': 'Geopolitical Analyst',
        'icon': '&#127757;',  # earth
        'color': '#553c9a',
    },
}

SYNTHESIS_META = {
    'cio_synthesis': {
        'name': 'CIO — S&iacute;ntesis',
        'role': 'Chief Investment Officer',
        'icon': '&#9733;',  # star
        'color': '#dd6b20',
    },
    'contrarian_critique': {
        'name': 'Contrarian — Desaf&iacute;o',
        'role': "Devil's Advocate",
        'icon': '&#9876;',  # crossed swords
        'color': '#9b2c2c',
    },
    'final_recommendation': {
        'name': 'Recomendaci&oacute;n Final',
        'role': 'Investment Committee Decision',
        'icon': '&#9998;',  # pencil
        'color': '#1a1a1a',
    },
}


def md_to_html(text: str) -> str:
    """Convierte markdown básico a HTML."""
    if not text:
        return ''
    lines = text.split('\n')
    html_lines = []
    in_table = False
    in_list = False
    table_rows = []

    for line in lines:
        stripped = line.strip()

        # Empty line
        if not stripped:
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            if in_table:
                html_lines.append(_render_table(table_rows))
                table_rows = []
                in_table = False
            html_lines.append('')
            continue

        # Table rows
        if '|' in stripped and stripped.startswith('|'):
            # Skip separator rows
            if re.match(r'^\|[\s\-:|]+\|$', stripped):
                in_table = True
                continue
            cells = [c.strip() for c in stripped.split('|')[1:-1]]
            if not in_table:
                in_table = True
            table_rows.append(cells)
            continue
        else:
            if in_table:
                html_lines.append(_render_table(table_rows))
                table_rows = []
                in_table = False

        # Headers
        if stripped.startswith('### '):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append(f'<h4 class="minutes-h4">{_inline_md(stripped[4:])}</h4>')
            continue
        if stripped.startswith('## '):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append(f'<h3 class="minutes-h3">{_inline_md(stripped[3:])}</h3>')
            continue
        if stripped.startswith('# '):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append(f'<h3 class="minutes-h3">{_inline_md(stripped[2:])}</h3>')
            continue

        # Horizontal rule
        if stripped == '---':
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            continue

        # List items
        if re.match(r'^[\-\*]\s', stripped):
            if not in_list:
                html_lines.append('<ul class="minutes-list">')
                in_list = True
            content = stripped[2:].strip()
            html_lines.append(f'<li>{_inline_md(content)}</li>')
            continue

        # Numbered list
        if re.match(r'^\d+\.\s', stripped):
            if not in_list:
                html_lines.append('<ul class="minutes-list minutes-ol">')
                in_list = True
            content = re.sub(r'^\d+\.\s', '', stripped)
            html_lines.append(f'<li>{_inline_md(content)}</li>')
            continue

        # Check items
        if stripped.startswith('✅') or stripped.startswith('❌'):
            html_lines.append(f'<div class="check-item">{_inline_md(stripped)}</div>')
            continue

        # Regular paragraph
        if in_list:
            html_lines.append('</ul>')
            in_list = False
        html_lines.append(f'<p>{_inline_md(stripped)}</p>')

    if in_list:
        html_lines.append('</ul>')
    if in_table:
        html_lines.append(_render_table(table_rows))

    return '\n'.join(html_lines)


def _render_table(rows: list) -> str:
    """Renderiza filas de tabla como HTML."""
    if not rows:
        return ''
    html = '<table class="minutes-table">'
    # First row as header
    html += '<thead><tr>'
    for cell in rows[0]:
        html += f'<th>{_inline_md(cell)}</th>'
    html += '</tr></thead><tbody>'
    for row in rows[1:]:
        html += '<tr>'
        for cell in row:
            html += f'<td>{_inline_md(cell)}</td>'
        html += '</tr>'
    html += '</tbody></table>'
    return html


def _inline_md(text: str) -> str:
    """Convierte markdown inline (bold, italic, code)."""
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # Italic
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    # Inline code
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    return text


def render_council_minutes(council_data: dict) -> str:
    """Genera HTML de minuta profesional desde council JSON."""

    meta = council_data.get('metadata', {})
    ts = meta.get('timestamp', '')
    try:
        dt = datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        dt = datetime.now()

    fecha = f"{dt.day} {MESES_ES.get(dt.month, '')} {dt.year}"
    duration = meta.get('duration_seconds', 0)
    duration_str = f"{int(duration // 60)}m {int(duration % 60)}s" if duration else 'N/A'
    model = meta.get('model', 'N/A')
    report_type = meta.get('report_type', 'general').upper()

    # Preflight
    preflight = council_data.get('preflight', {})
    verdict = preflight.get('overall_verdict', 'N/A')
    verdict_class = {
        'GO': 'verdict-go', 'CAUTION': 'verdict-caution', 'NO_GO': 'verdict-nogo'
    }.get(verdict, '')
    modules = preflight.get('modules', {})

    # Panel outputs
    panel = council_data.get('panel_outputs', {})
    panel_order = ['macro', 'rv', 'rf', 'riesgo', 'geo']

    # Synthesis
    cio = council_data.get('cio_synthesis', '')
    contrarian = council_data.get('contrarian_critique', '')
    final = council_data.get('final_recommendation', '')

    # Build HTML
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Greybark Research - Minuta AI Council</title>
    <style>
        :root {{
            --primary: #1a1a1a;
            --accent: #dd6b20;
            --text: #1a1a1a;
            --text-med: #4a4a4a;
            --text-light: #717171;
            --bg-light: #f7f7f7;
            --border: #e0e0e0;
            --green: #276749;
            --red: #c53030;
            --yellow: #d69e2e;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
            font-size: 10pt;
            line-height: 1.55;
            color: var(--text);
            background: white;
        }}
        .container {{ max-width: 1000px; margin: 0 auto; padding: 25px 40px; }}

        /* Header */
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            border-bottom: 3px solid var(--primary);
            padding-bottom: 15px;
            margin-bottom: 10px;
        }}
        .header h1 {{
            font-size: 22pt;
            font-weight: 900;
            letter-spacing: 1px;
            text-transform: uppercase;
            color: var(--primary);
        }}
        .header .subtitle {{
            font-size: 11pt;
            color: var(--accent);
            font-weight: 600;
            margin-top: 2px;
        }}
        .header .date-box {{
            text-align: right;
            font-size: 9pt;
            color: var(--text-med);
        }}
        .header .date-box .fecha {{
            font-size: 12pt;
            font-weight: 700;
            color: var(--primary);
        }}

        /* Meta bar */
        .meta-bar {{
            display: flex;
            gap: 20px;
            background: var(--bg-light);
            padding: 10px 15px;
            border-radius: 4px;
            margin-bottom: 25px;
            font-size: 9pt;
            color: var(--text-med);
            flex-wrap: wrap;
        }}
        .meta-bar strong {{ color: var(--text); }}

        /* Verdict badges */
        .verdict {{ display: inline-block; padding: 2px 10px; border-radius: 3px; font-weight: 700; font-size: 9pt; }}
        .verdict-go {{ background: #f0fff4; color: var(--green); border: 1px solid #c6f6d5; }}
        .verdict-caution {{ background: #fffff0; color: #b7791f; border: 1px solid #fefcbf; }}
        .verdict-nogo {{ background: #fff5f5; color: var(--red); border: 1px solid #fed7d7; }}

        /* Sections */
        .section {{ margin-bottom: 30px; page-break-inside: avoid; }}
        .section-title {{
            font-size: 13pt;
            font-weight: 700;
            color: var(--primary);
            border-bottom: 2px solid var(--accent);
            padding-bottom: 5px;
            margin-bottom: 15px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        /* Agent cards */
        .agent-card {{
            border: 1px solid var(--border);
            border-radius: 6px;
            margin-bottom: 20px;
            overflow: hidden;
        }}
        .agent-header {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 16px;
            color: white;
            font-size: 10pt;
        }}
        .agent-icon {{ font-size: 16pt; }}
        .agent-name {{ font-weight: 700; font-size: 11pt; }}
        .agent-role {{ font-size: 8.5pt; opacity: 0.85; margin-left: auto; }}
        .agent-body {{ padding: 15px 20px; }}
        .agent-body p {{ margin-bottom: 8px; }}

        /* Synthesis cards */
        .synthesis-card {{
            border: 2px solid var(--border);
            border-radius: 6px;
            margin-bottom: 20px;
            overflow: hidden;
        }}
        .synthesis-header {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 12px 18px;
            color: white;
            font-size: 11pt;
        }}
        .synthesis-body {{ padding: 18px 22px; }}
        .synthesis-body p {{ margin-bottom: 8px; }}

        /* Minutes content styling */
        .minutes-h3 {{
            font-size: 10.5pt;
            font-weight: 700;
            color: var(--accent);
            border-left: 3px solid var(--accent);
            padding-left: 8px;
            margin: 14px 0 8px 0;
        }}
        .minutes-h4 {{
            font-size: 10pt;
            font-weight: 700;
            color: var(--text);
            margin: 10px 0 6px 0;
        }}
        .minutes-list {{
            margin: 6px 0 10px 18px;
            font-size: 9.5pt;
        }}
        .minutes-list li {{
            margin-bottom: 4px;
            line-height: 1.5;
        }}
        .minutes-ol {{ list-style-type: decimal; }}
        .check-item {{
            padding: 4px 0;
            font-size: 9.5pt;
        }}

        /* Tables inside minutes */
        .minutes-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 9pt;
            margin: 10px 0;
        }}
        .minutes-table th {{
            background: var(--primary);
            color: white;
            padding: 6px 10px;
            text-align: left;
            font-size: 8pt;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }}
        .minutes-table td {{
            padding: 6px 10px;
            border-bottom: 1px solid var(--border);
        }}
        .minutes-table tr:nth-child(even) {{ background: var(--bg-light); }}

        /* Preflight mini table */
        .preflight-grid {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 6px;
            margin-top: 8px;
        }}
        .pf-module {{
            background: var(--bg-light);
            border-radius: 4px;
            padding: 6px 8px;
            font-size: 8pt;
            text-align: center;
        }}
        .pf-green {{ border-bottom: 3px solid var(--green); }}
        .pf-yellow {{ border-bottom: 3px solid var(--yellow); }}
        .pf-red {{ border-bottom: 3px solid var(--red); }}

        /* Table of contents */
        .toc {{
            background: var(--bg-light);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 15px 20px;
            margin-bottom: 25px;
        }}
        .toc-title {{
            font-weight: 700;
            font-size: 9pt;
            text-transform: uppercase;
            color: var(--text-light);
            margin-bottom: 8px;
            letter-spacing: 0.5px;
        }}
        .toc-items {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 4px 30px;
        }}
        .toc-item {{
            font-size: 9pt;
            color: var(--text-med);
            padding: 2px 0;
        }}
        .toc-item .num {{
            display: inline-block;
            width: 22px;
            font-weight: 700;
            color: var(--accent);
        }}

        /* Footer */
        .footer {{
            margin-top: 30px;
            padding-top: 12px;
            border-top: 2px solid var(--primary);
            display: flex;
            justify-content: space-between;
            font-size: 8pt;
            color: var(--text-light);
        }}

        /* Print */
        @media print {{
            body {{ font-size: 9pt; }}
            .container {{ padding: 10px 20px; }}
            .agent-card, .synthesis-card {{ page-break-inside: avoid; }}
        }}
    </style>
</head>
<body>
<div class="container">

    <!-- HEADER -->
    <div class="header">
        <div>
            <h1>Greybark Research</h1>
            <div class="subtitle">Minuta del AI Council &mdash; Sesi&oacute;n {report_type}</div>
        </div>
        <div class="date-box">
            <div class="fecha">{fecha}</div>
            <div>Duraci&oacute;n: {duration_str}</div>
            <div>Modelo: {model}</div>
        </div>
    </div>

    <!-- META BAR -->
    <div class="meta-bar">
        <div><strong>Tipo:</strong> {report_type}</div>
        <div><strong>Agentes Panel:</strong> {len(panel)}</div>
        <div><strong>Capas:</strong> Panel &rarr; CIO &rarr; Contrarian &rarr; Final</div>
        <div><strong>Preflight:</strong> <span class="verdict {verdict_class}">{verdict}</span></div>
    </div>

    <!-- TABLE OF CONTENTS -->
    <div class="toc">
        <div class="toc-title">&Iacute;ndice de la Sesi&oacute;n</div>
        <div class="toc-items">
            <div class="toc-item"><span class="num">1</span>Preflight &amp; Validaci&oacute;n</div>
            <div class="toc-item"><span class="num">5</span>S&iacute;ntesis CIO</div>
            <div class="toc-item"><span class="num">2-4</span>Panel de Especialistas (5 agentes)</div>
            <div class="toc-item"><span class="num">6</span>Desaf&iacute;o Contrarian</div>
            <div class="toc-item"><span class="num"></span></div>
            <div class="toc-item"><span class="num">7</span>Recomendaci&oacute;n Final</div>
        </div>
    </div>
"""

    # PREFLIGHT SECTION
    html += '    <div class="section">\n'
    html += '        <div class="section-title">1. Preflight &amp; Validaci&oacute;n de Datos</div>\n'
    if modules:
        html += '        <div class="preflight-grid">\n'
        for mod_name, mod_data in modules.items():
            status = mod_data.get('status', 'GREEN')
            css_class = {'GREEN': 'pf-green', 'YELLOW': 'pf-yellow', 'RED': 'pf-red'}.get(status, 'pf-green')
            criticality = mod_data.get('criticality', '')
            detail = mod_data.get('detail', '')
            html += f'            <div class="pf-module {css_class}"><strong>{mod_name}</strong><br>{criticality}<br><span style="font-size:7pt;color:#717171">{detail}</span></div>\n'
        html += '        </div>\n'
    else:
        html += '        <p style="color:#717171; font-size:9pt;">Sin datos de preflight.</p>\n'
    html += '    </div>\n\n'

    # PANEL SECTION
    html += '    <div class="section">\n'
    html += '        <div class="section-title">2-4. Panel de Especialistas</div>\n'

    for i, agent_key in enumerate(panel_order):
        if agent_key not in panel:
            continue
        agent = AGENT_META.get(agent_key, {
            'name': agent_key.upper(),
            'role': 'Specialist',
            'icon': '&#9679;',
            'color': '#4a4a4a',
        })
        content_html = md_to_html(panel[agent_key])

        html += f'''        <div class="agent-card">
            <div class="agent-header" style="background:{agent['color']}">
                <span class="agent-icon">{agent['icon']}</span>
                <span class="agent-name">{agent['name']}</span>
                <span class="agent-role">{agent['role']}</span>
            </div>
            <div class="agent-body">
                {content_html}
            </div>
        </div>
'''

    html += '    </div>\n\n'

    # SYNTHESIS SECTIONS
    synthesis_parts = [
        ('5', 'cio_synthesis', cio),
        ('6', 'contrarian_critique', contrarian),
        ('7', 'final_recommendation', final),
    ]

    for num, key, content in synthesis_parts:
        if not content:
            continue
        meta_info = SYNTHESIS_META.get(key, {
            'name': key, 'role': '', 'icon': '&#9679;', 'color': '#4a4a4a'
        })
        content_html = md_to_html(content)

        html += f'''    <div class="section">
        <div class="section-title">{num}. {meta_info['name']}</div>
        <div class="synthesis-card">
            <div class="synthesis-header" style="background:{meta_info['color']}">
                <span class="agent-icon">{meta_info['icon']}</span>
                <span class="agent-name">{meta_info['name']}</span>
                <span class="agent-role">{meta_info['role']}</span>
            </div>
            <div class="synthesis-body">
                {content_html}
            </div>
        </div>
    </div>

'''

    # FOOTER
    html += f"""    <!-- FOOTER -->
    <div class="footer">
        <div>Greybark Research &mdash; AI Council Minutes &mdash; {fecha} &mdash; {duration_str}</div>
        <div style="font-style:italic">Documento generado autom&aacute;ticamente. Uso interno exclusivo.</div>
    </div>

</div>
</body>
</html>"""

    return html


# =========================================================================
# CLI
# =========================================================================

if __name__ == '__main__':
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except AttributeError:
            pass

    base = Path(__file__).parent
    council_dir = base / "output" / "council"
    reports_dir = base / "output" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Find input file
    if len(sys.argv) > 1:
        json_path = Path(sys.argv[1])
    else:
        files = sorted(council_dir.glob("council_result_*.json"), reverse=True)
        # Skip small/aborted files
        json_path = None
        for f in files:
            if f.stat().st_size > 15000:
                json_path = f
                break
        if not json_path and files:
            json_path = files[0]

    if not json_path or not json_path.exists():
        print("No council result found.")
        sys.exit(1)

    print(f"Reading: {json_path.name} ({json_path.stat().st_size / 1024:.0f} KB)")

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    html = render_council_minutes(data)

    # Output filename
    stem = json_path.stem.replace('council_result_', '')
    out_path = reports_dir / f"council_minutes_{stem}.html"
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Generated: {out_path}")
    print(f"Size: {out_path.stat().st_size / 1024:.0f} KB")

    # Open in browser
    if '--no-open' not in sys.argv:
        import os
        os.startfile(str(out_path))
        print("Opened in browser.")
