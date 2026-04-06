"""
TAA Report Section — Generates HTML for the "Herramienta Cuantitativa" section
in the Asset Allocation report.

Renders:
  - Stress gauge (SVG)
  - Tilts bar chart (inline base64 PNG)
  - Track record metrics table
  - Regime badge
  - Concordance table (TAA vs Council) when council views are available
"""
import base64
import io
from typing import Dict, Any, Optional, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np


# ── Colors (matching Greybark report design) ─────────────────────────
OW_GREEN = "#276749"
UW_RED = "#c53030"
NEUTRAL_AMBER = "#744210"
BG_DARK = "#1a1a2e"
TEXT_LIGHT = "#8b949e"
TEXT_WHITE = "#e6edf3"
ACCENT = "#dd6b20"
GRID_COLOR = "#2d3139"


def render_quant_tool_section(taa_data: Dict[str, Any],
                               council_views: Dict[str, Any] = None) -> str:
    """Generate full HTML for the Herramienta Cuantitativa section.

    Args:
        taa_data: output from TAADataCollector.collect_all()
        council_views: parsed council EQUITY_VIEWS / FI_POSITIONING for concordance
    """
    if not taa_data or 'error' in taa_data:
        return ''

    parts = []

    # Row 1: Stress gauge + Regime + Track record
    parts.append('<div style="display:flex; gap:20px; margin-bottom:20px; flex-wrap:wrap;">')
    parts.append(_render_stress_box(taa_data.get('stress', {})))
    parts.append(_render_regime_box(taa_data.get('regime', {})))
    parts.append(_render_track_record_box(taa_data.get('backtest_metrics', {})))
    parts.append('</div>')

    # Row 2: Tilts chart + Tilts table
    parts.append('<div style="display:flex; gap:20px; margin-bottom:20px; flex-wrap:wrap;">')
    parts.append(_render_tilts_chart(taa_data.get('tilts', {})))
    parts.append(_render_tilts_table(taa_data.get('tilts', {})))
    parts.append('</div>')

    # Row 3: Leading indicators
    parts.append(_render_leading_indicators(taa_data.get('stress', {})))

    # Row 4: Concordance (if council views available)
    if council_views:
        parts.append(_render_concordance(taa_data.get('tilts', {}), council_views))

    return '\n'.join(parts)


# ── Stress Box ────────────────────────────────────────────────────────

def _render_stress_box(stress: Dict) -> str:
    if 'error' in stress:
        return ''

    score = stress.get('score', 0)
    level = stress.get('level', 'N/A')

    # Color by level
    color_map = {'LOW': '#3fb950', 'MEDIUM': '#d29922', 'HIGH': '#f85149', 'CRITICAL': '#ff0040'}
    color = color_map.get(level, '#8b949e')
    level_es = {'LOW': 'BAJO', 'MEDIUM': 'MEDIO', 'HIGH': 'ALTO', 'CRITICAL': 'CRÍTICO'}.get(level, level)

    # SVG gauge
    pct = min(score, 1.0)
    angle = 180 * pct  # 0=left, 180=right
    rad = np.radians(180 - angle)
    nx = 50 + 35 * np.cos(rad)
    ny = 55 - 35 * np.sin(rad)

    svg = f'''<svg viewBox="0 0 100 65" width="160" height="110" style="display:block;margin:0 auto;">
      <path d="M 10 55 A 40 40 0 0 1 90 55" fill="none" stroke="#2d3139" stroke-width="8" stroke-linecap="round"/>
      <path d="M 10 55 A 40 40 0 0 1 90 55" fill="none" stroke="url(#gauge-grad)" stroke-width="8" stroke-linecap="round"
            stroke-dasharray="{pct * 126:.0f} 126"/>
      <circle cx="{nx:.1f}" cy="{ny:.1f}" r="4" fill="{color}"/>
      <text x="50" y="52" text-anchor="middle" font-size="14" font-weight="bold" fill="{color}">{score:.2f}</text>
      <text x="50" y="63" text-anchor="middle" font-size="7" fill="{TEXT_LIGHT}">{level_es}</text>
      <defs><linearGradient id="gauge-grad" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="#3fb950"/><stop offset="50%" stop-color="#d29922"/>
        <stop offset="100%" stop-color="#f85149"/>
      </linearGradient></defs>
    </svg>'''

    return f'''<div style="flex:1;min-width:180px;background:#161b22;border:1px solid #30363d;
                border-radius:8px;padding:12px;text-align:center;">
      <div style="font-size:10px;color:{TEXT_LIGHT};text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">
        Score de Estrés</div>
      {svg}
    </div>'''


# ── Regime Box ────────────────────────────────────────────────────────

def _render_regime_box(regime: Dict) -> str:
    if 'error' in regime:
        return ''

    current = regime.get('current', 'N/A')
    regime_colors = {
        'EXPANSION': '#3fb950', 'RECOVERY': '#58a6ff',
        'SLOWDOWN': '#d29922', 'RECESSION': '#f85149'
    }
    regime_es = {
        'EXPANSION': 'Expansión', 'RECOVERY': 'Recuperación',
        'SLOWDOWN': 'Desaceleración', 'RECESSION': 'Recesión'
    }
    color = regime_colors.get(current, '#8b949e')

    return f'''<div style="flex:1;min-width:180px;background:#161b22;border:1px solid #30363d;
                border-radius:8px;padding:12px;text-align:center;">
      <div style="font-size:10px;color:{TEXT_LIGHT};text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">
        Régimen Detectado</div>
      <div style="font-size:22px;font-weight:bold;color:{color};margin:12px 0;">
        {regime_es.get(current, current)}</div>
      <div style="font-size:9px;color:{TEXT_LIGHT};">
        Basado en curva de rendimiento, Sahm Rule e indicadores líderes</div>
    </div>'''


# ── Track Record Box ──────────────────────────────────────────────────

def _render_track_record_box(bt: Dict) -> str:
    if 'error' in bt:
        return ''

    rows = [
        ("Information Ratio", bt.get('information_ratio', 'N/A')),
        ("Excess Return (ann)", bt.get('excess_return_ann', 'N/A')),
        ("Hit Rate", bt.get('hit_rate', 'N/A')),
        ("Tracking Error", bt.get('tracking_error', 'N/A')),
        ("Sharpe Activo", bt.get('active_sharpe', 'N/A')),
        ("Max Drawdown", bt.get('max_drawdown_active', 'N/A')),
        ("Período", bt.get('period', 'N/A')),
    ]

    rows_html = ''.join(
        f'<tr><td style="color:{TEXT_LIGHT};font-size:9px;padding:2px 6px;">{k}</td>'
        f'<td style="color:{TEXT_WHITE};font-size:9px;padding:2px 6px;text-align:right;font-weight:600;">{v}</td></tr>'
        for k, v in rows
    )

    return f'''<div style="flex:1.5;min-width:220px;background:#161b22;border:1px solid #30363d;
                border-radius:8px;padding:12px;">
      <div style="font-size:10px;color:{TEXT_LIGHT};text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">
        Track Record Modelo</div>
      <table style="width:100%;border-collapse:collapse;">{rows_html}</table>
    </div>'''


# ── Tilts Chart (matplotlib → base64 PNG) ─────────────────────────────

def _render_tilts_chart(tilts_data: Dict) -> str:
    if 'error' in tilts_data:
        return ''

    items = tilts_data.get('tilts_formatted', [])
    if not items:
        return ''

    # Sort by tilt value
    items_sorted = sorted(items, key=lambda x: float(x['tilt_pct'].replace('%', '').replace('+', '')) / 100)

    tickers = [i['asset'] for i in items_sorted]
    values = [float(i['tilt_pct'].replace('%', '').replace('+', '')) for i in items_sorted]
    colors = [OW_GREEN if v > 0.1 else UW_RED if v < -0.1 else '#555' for v in values]

    fig, ax = plt.subplots(figsize=(4.5, 5.5))
    fig.patch.set_facecolor('#0e1117')
    ax.set_facecolor('#0e1117')

    ax.barh(tickers, values, color=colors, height=0.6, edgecolor='none')
    ax.axvline(0, color='#30363d', linewidth=0.8)
    ax.set_xlabel('Tilt (%)', fontsize=8, color=TEXT_LIGHT)
    ax.tick_params(axis='y', labelsize=7, colors=TEXT_LIGHT)
    ax.tick_params(axis='x', labelsize=7, colors=TEXT_LIGHT)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color('#2d3139')
    ax.spines['left'].set_color('#2d3139')
    ax.grid(axis='x', color='#21262d', alpha=0.5)

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode('utf-8')

    return f'''<div style="flex:1;min-width:280px;background:#161b22;border:1px solid #30363d;
                border-radius:8px;padding:12px;">
      <div style="font-size:10px;color:{TEXT_LIGHT};text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">
        Sesgos Tácticos vs Benchmark</div>
      <img src="data:image/png;base64,{b64}" style="width:100%;border-radius:4px;" alt="TAA Tilts"/>
    </div>'''


# ── Tilts Table by Asset Class ────────────────────────────────────────

def _render_tilts_table(tilts_data: Dict) -> str:
    by_class = tilts_data.get('tilts_by_class', {})
    if not by_class:
        return ''

    rows_html = ''
    for ac, info in by_class.items():
        if not isinstance(info, dict):
            continue
        direction = info.get('direction', 'N')
        badge_color = OW_GREEN if direction == 'OW' else UW_RED if direction == 'UW' else NEUTRAL_AMBER
        rows_html += f'''<tr>
          <td style="padding:4px 8px;font-size:9px;border-bottom:1px solid #21262d;">{ac}</td>
          <td style="padding:4px 8px;font-size:9px;text-align:center;border-bottom:1px solid #21262d;">
            <span style="background:{badge_color};color:white;padding:1px 6px;border-radius:3px;font-size:8px;font-weight:600;">
              {direction}</span></td>
          <td style="padding:4px 8px;font-size:9px;text-align:right;border-bottom:1px solid #21262d;font-weight:600;">
            {info.get('avg_tilt', '')}</td>
          <td style="padding:4px 8px;font-size:8px;color:{TEXT_LIGHT};border-bottom:1px solid #21262d;">
            {info.get('top_assets', '')}</td>
        </tr>'''

    return f'''<div style="flex:1;min-width:300px;background:#161b22;border:1px solid #30363d;
                border-radius:8px;padding:12px;">
      <div style="font-size:10px;color:{TEXT_LIGHT};text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">
        Sesgos por Clase de Activo</div>
      <table style="width:100%;border-collapse:collapse;">
        <thead><tr style="border-bottom:2px solid #30363d;">
          <th style="text-align:left;padding:4px 8px;font-size:8px;color:{TEXT_LIGHT};">Clase</th>
          <th style="text-align:center;padding:4px 8px;font-size:8px;color:{TEXT_LIGHT};">View</th>
          <th style="text-align:right;padding:4px 8px;font-size:8px;color:{TEXT_LIGHT};">Tilt Prom.</th>
          <th style="text-align:left;padding:4px 8px;font-size:8px;color:{TEXT_LIGHT};">Principales</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>'''


# ── Leading Indicators ────────────────────────────────────────────────

def _render_leading_indicators(stress: Dict) -> str:
    components = stress.get('components', {})
    if not components:
        return ''

    signal_colors = {
        'calm': '#3fb950', 'positive': '#3fb950', 'falling': '#3fb950', 'expansion': '#3fb950',
        'neutral': '#d29922', 'stable': '#d29922', 'normal': '#d29922', 'flat': '#d29922',
        'elevated': '#d29922',
        'stress': '#f85149', 'inverted': '#f85149', 'rising': '#f85149',
        'contraction': '#f85149', 'wide': '#f85149',
    }

    indicators_html = ''
    for name, info in components.items():
        if not isinstance(info, dict):
            continue
        signal = info.get('signal', 'neutral')
        color = signal_colors.get(signal, '#8b949e')
        label = name.replace('_', ' ').title()
        value = info.get('value', 'N/A')
        extra = info.get('chg_6m', '')
        if extra:
            extra = f' ({extra})'

        indicators_html += f'''<div style="flex:1;min-width:120px;text-align:center;padding:6px;">
          <div style="font-size:8px;color:{TEXT_LIGHT};text-transform:uppercase;">{label}</div>
          <div style="font-size:14px;font-weight:bold;color:{color};margin:2px 0;">{value}{extra}</div>
          <div style="font-size:7px;color:{color};text-transform:uppercase;">{signal}</div>
        </div>'''

    return f'''<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px;margin-bottom:20px;">
      <div style="font-size:10px;color:{TEXT_LIGHT};text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">
        Indicadores Líderes (Componentes del Score de Estrés)</div>
      <div style="display:flex;flex-wrap:wrap;gap:4px;">{indicators_html}</div>
    </div>'''


# ── Concordance Table ─────────────────────────────────────────────────

def _render_concordance(tilts_data: Dict, council_views: Dict) -> str:
    """Compare TAA tilts vs council views."""
    by_class = tilts_data.get('tilts_by_class', {})
    if not by_class or not council_views:
        return ''

    rows_html = ''
    for ac, taa_info in by_class.items():
        if not isinstance(taa_info, dict):
            continue
        taa_dir = taa_info.get('direction', 'N')

        # Try to find matching council view
        council_dir = council_views.get(ac, {}).get('direction', '')

        if not council_dir:
            concordance = '—'
            conc_color = TEXT_LIGHT
        elif taa_dir == council_dir:
            concordance = 'Coincide'
            conc_color = '#3fb950'
        elif (taa_dir == 'N' or council_dir == 'N'):
            concordance = 'Parcial'
            conc_color = '#d29922'
        else:
            concordance = 'Diverge'
            conc_color = '#f85149'

        taa_badge = OW_GREEN if taa_dir == 'OW' else UW_RED if taa_dir == 'UW' else NEUTRAL_AMBER
        council_badge = OW_GREEN if council_dir == 'OW' else UW_RED if council_dir == 'UW' else NEUTRAL_AMBER

        rows_html += f'''<tr>
          <td style="padding:4px 8px;font-size:9px;border-bottom:1px solid #21262d;">{ac}</td>
          <td style="padding:4px 8px;text-align:center;border-bottom:1px solid #21262d;">
            <span style="background:{taa_badge};color:white;padding:1px 6px;border-radius:3px;font-size:8px;font-weight:600;">
              {taa_dir}</span> {taa_info.get('avg_tilt', '')}</td>
          <td style="padding:4px 8px;text-align:center;border-bottom:1px solid #21262d;">
            <span style="background:{council_badge};color:white;padding:1px 6px;border-radius:3px;font-size:8px;font-weight:600;">
              {council_dir or "—"}</span></td>
          <td style="padding:4px 8px;text-align:center;border-bottom:1px solid #21262d;
                     font-weight:600;color:{conc_color};font-size:9px;">{concordance}</td>
        </tr>'''

    return f'''<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px;">
      <div style="font-size:10px;color:{TEXT_LIGHT};text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">
        Concordancia: Modelo Cuantitativo vs Comité de Inversión</div>
      <table style="width:100%;border-collapse:collapse;">
        <thead><tr style="border-bottom:2px solid #30363d;">
          <th style="text-align:left;padding:4px 8px;font-size:8px;color:{TEXT_LIGHT};">Clase de Activo</th>
          <th style="text-align:center;padding:4px 8px;font-size:8px;color:{TEXT_LIGHT};">Modelo TAA</th>
          <th style="text-align:center;padding:4px 8px;font-size:8px;color:{TEXT_LIGHT};">Comité</th>
          <th style="text-align:center;padding:4px 8px;font-size:8px;color:{TEXT_LIGHT};">Concordancia</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
      <p style="font-size:8px;color:{TEXT_LIGHT};margin-top:8px;">
        Las divergencias no son necesariamente negativas — reflejan que el Comité incorpora información
        cualitativa (geopolítica, flujos, eventos) que el modelo cuantitativo no captura.
      </p>
    </div>'''
