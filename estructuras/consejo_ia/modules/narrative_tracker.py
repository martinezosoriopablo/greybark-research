# -*- coding: utf-8 -*-
"""
Greybark Research - Narrative Tracker Module
============================================
Tracks 5 narrative dimensions across AI Council sessions.
Detects shifts and visualizes evolution over time.

Usage:
    from modules.narrative_tracker import NarrativeTracker
    nt = NarrativeTracker()
    result = nt.run()
"""

from datetime import datetime
from typing import Dict, Any, List, Optional

from .base_module import AnalyticsModuleBase, HAS_MPL
from .narrative_parser import load_all_sessions, NarrativeDimensions

if HAS_MPL:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np


class NarrativeTracker(AnalyticsModuleBase):

    MODULE_NAME = "narrative_tracker"

    # Dimensions to track with their display names and value palettes
    DIMENSIONS = {
        'regime_call': {
            'label': 'Regimen',
            'values': ['EXPANSION', 'LATE_CYCLE', 'TRANSITION', 'MODERATE', 'SLOWDOWN', 'RECESSION', 'STAGFLATION'],
            'colors': {
                'EXPANSION': '#276749', 'LATE_CYCLE': '#d69e2e',
                'TRANSITION': '#dd6b20', 'MODERATE': '#805ad5',
                'SLOWDOWN': '#dd6b20', 'RECESSION': '#c53030',
                'STAGFLATION': '#c53030',
            },
        },
        'risk_level': {
            'label': 'Nivel de Riesgo',
            'values': ['LOW', 'MODERATE', 'NORMAL', 'ELEVATED', 'HIGH'],
            'colors': {
                'LOW': '#276749', 'MODERATE': '#d69e2e', 'NORMAL': '#276749',
                'ELEVATED': '#dd6b20', 'HIGH': '#c53030',
            },
        },
        'fed_stance': {
            'label': 'Stance Fed',
            'values': ['DOVISH', 'NEUTRAL', 'HAWKISH'],
            'colors': {
                'DOVISH': '#276749', 'NEUTRAL': '#d69e2e', 'HAWKISH': '#c53030',
            },
        },
        'chile_positioning': {
            'label': 'Chile Posicionamiento',
            'values': ['UW', 'N', 'OW'],
            'colors': {
                'UW': '#c53030', 'N': '#d69e2e', 'OW': '#276749',
            },
        },
        'equity_conviction': {
            'label': 'Conviccion Equity',
            'values': ['BAJA', 'MEDIA', 'ALTA'],
            'colors': {
                'BAJA': '#c53030', 'MEDIA': '#d69e2e', 'ALTA': '#276749',
            },
        },
    }

    # ── Data collection ─────────────────────────────────────

    def _collect_data(self) -> Dict:
        sessions = load_all_sessions()
        self._print(f"  Loaded {len(sessions)} sessions")
        return {'sessions': sessions}

    # ── Computation ─────────────────────────────────────────

    def _compute(self) -> Dict:
        sessions: List[NarrativeDimensions] = self._data.get('sessions', [])
        if not sessions:
            return {'error': 'No council sessions found'}

        timelines = {}
        shifts_all = {}
        current_state = {}

        for dim_key, dim_info in self.DIMENSIONS.items():
            timeline = []
            for s in sessions:
                val = getattr(s, dim_key, None)
                if val is not None:
                    timeline.append({
                        'date': s.session_date,
                        'value': val,
                        'file': s.source_file,
                    })

            timelines[dim_key] = timeline

            # Detect shifts
            shifts = []
            for i in range(1, len(timeline)):
                if timeline[i]['value'] != timeline[i - 1]['value']:
                    shifts.append({
                        'date': timeline[i]['date'],
                        'from': timeline[i - 1]['value'],
                        'to': timeline[i]['value'],
                    })
            shifts_all[dim_key] = shifts

            # Current state
            if timeline:
                current_state[dim_key] = timeline[-1]['value']

        # Recent shifts (from last 2 sessions worth of data)
        recent_shifts = {}
        for dim_key, shifts in shifts_all.items():
            if shifts:
                recent_shifts[dim_key] = shifts[-1]

        # Date range
        dates = [s.session_date for s in sessions]
        date_range = f"{dates[0]} to {dates[-1]}" if dates else "N/A"

        return {
            'n_sessions': len(sessions),
            'date_range': date_range,
            'timelines': timelines,
            'shifts': shifts_all,
            'current_state': current_state,
            'recent_shifts': recent_shifts,
        }

    # ── Chart: Swim lane timeline ───────────────────────────

    def _generate_chart(self) -> str:
        if not HAS_MPL or 'error' in self._result:
            return self._create_placeholder("Narrative Tracker")

        timelines = self._result.get('timelines', {})
        shifts = self._result.get('shifts', {})
        dim_keys = list(self.DIMENSIONS.keys())
        n_dims = len(dim_keys)

        if not any(timelines.get(k) for k in dim_keys):
            return self._create_placeholder("Narrative Tracker (sin datos)")

        fig, axes = plt.subplots(n_dims, 1, figsize=(8, 1.8 * n_dims),
                                  sharex=True)
        if n_dims == 1:
            axes = [axes]

        # Collect all dates for x-axis
        all_dates = set()
        for tl in timelines.values():
            for pt in tl:
                all_dates.add(pt['date'])
        all_dates = sorted(all_dates)
        date_to_x = {d: i for i, d in enumerate(all_dates)}

        for idx, dim_key in enumerate(dim_keys):
            ax = axes[idx]
            dim_info = self.DIMENSIONS[dim_key]
            timeline = timelines.get(dim_key, [])
            dim_shifts = shifts.get(dim_key, [])
            shift_dates = {s['date'] for s in dim_shifts}

            values = dim_info['values']
            val_to_y = {v: i for i, v in enumerate(values)}

            if timeline:
                xs = [date_to_x.get(pt['date'], 0) for pt in timeline]
                ys = [val_to_y.get(pt['value'], 0) for pt in timeline]
                colors_pt = [dim_info['colors'].get(pt['value'], '#718096') for pt in timeline]

                # Lines connecting points
                ax.plot(xs, ys, '-', color='#cbd5e0', linewidth=1, zorder=1)

                # Points
                for i, (x, y, c, pt) in enumerate(zip(xs, ys, colors_pt, timeline)):
                    is_shift = pt['date'] in shift_dates
                    ms = 10 if is_shift else 7
                    edge = '#c53030' if is_shift else 'white'
                    ew = 2 if is_shift else 1
                    ax.plot(x, y, 'o', color=c, markersize=ms,
                            markeredgecolor=edge, markeredgewidth=ew, zorder=3)

            ax.set_yticks(range(len(values)))
            ax.set_yticklabels(values, fontsize=7)
            ax.set_ylabel(dim_info['label'], fontsize=8, fontweight='bold',
                          color=self.COLORS['primary'])
            ax.set_ylim(-0.5, len(values) - 0.5)
            ax.grid(axis='x', alpha=0.2)
            for spine in ['top', 'right']:
                ax.spines[spine].set_visible(False)

        # X-axis labels on bottom
        if all_dates:
            axes[-1].set_xticks(range(len(all_dates)))
            axes[-1].set_xticklabels(
                [d[5:] for d in all_dates],  # MM-DD
                fontsize=7, rotation=45, ha='right',
            )

        fig.suptitle('Narrative Tracker — Evolucion del Consejo',
                     fontsize=11, fontweight='bold', color=self.COLORS['primary'], y=0.99)
        fig.tight_layout()
        return self._fig_to_base64(fig)

    # ── Report section (HTML) ───────────────────────────────

    def get_report_section(self) -> str:
        if not self._result or 'error' in self._result:
            return '<div style="color:#718096;">Narrative Tracker: datos no disponibles</div>'

        r = self._result
        chart = self._chart or self._create_placeholder("Narrative Tracker")
        chart_img = f'<img src="{chart}" style="max-width:100%;"/>' if chart.startswith('data:') else chart

        # Current state
        state_rows = ''
        for dim_key, dim_info in self.DIMENSIONS.items():
            val = r['current_state'].get(dim_key, 'N/A')
            color = dim_info['colors'].get(val, self.COLORS['text_medium'])
            state_rows += (
                f'<tr>'
                f'<td style="padding:3px 8px;font-size:11px;">{dim_info["label"]}</td>'
                f'<td style="padding:3px 8px;font-size:11px;font-weight:700;color:{color};">{val}</td>'
                f'</tr>'
            )

        # Recent shifts
        shift_html = ''
        for dim_key, shift in r.get('recent_shifts', {}).items():
            label = self.DIMENSIONS[dim_key]['label']
            shift_html += (
                f'<div style="font-size:11px;margin:2px 0;">'
                f'<span style="font-weight:600;">{label}:</span> '
                f'{shift["from"]} → {shift["to"]} '
                f'<span style="color:{self.COLORS["text_light"]};">(desde {shift["date"]})</span>'
                f'</div>'
            )
        if not shift_html:
            shift_html = '<div style="font-size:11px;color:#718096;">Sin cambios recientes</div>'

        return (
            f'<div style="margin:20px 0;">'
            f'<div style="font-size:16px;font-weight:700;color:{self.COLORS["primary"]};'
            f'border-bottom:2px solid {self.COLORS["accent"]};padding-bottom:6px;margin-bottom:12px;">'
            f'Narrative Tracker</div>'
            f'<div style="font-size:11px;color:{self.COLORS["text_light"]};margin-bottom:8px;">'
            f'{r["n_sessions"]} sesiones analizadas ({r["date_range"]})</div>'
            f'<div style="text-align:center;margin:10px 0;">{chart_img}</div>'
            f'<div style="display:flex;gap:20px;margin:12px 0;">'
            f'<div style="flex:1;">'
            f'<div style="font-size:12px;font-weight:700;margin-bottom:6px;">Estado Actual</div>'
            f'<table style="width:100%;border-collapse:collapse;">{state_rows}</table></div>'
            f'<div style="flex:1;">'
            f'<div style="font-size:12px;font-weight:700;margin-bottom:6px;">Cambios Recientes</div>'
            f'{shift_html}</div></div>'
            f'</div>'
        )

    # ── Council input (plain text) ──────────────────────────

    def get_council_input(self) -> str:
        if not self._result or 'error' in self._result:
            return "[NARRATIVE TRACKER MODULE] Data unavailable.\n"

        r = self._result
        lines = [
            "[NARRATIVE TRACKER MODULE]",
            f"Sessions analyzed: {r['n_sessions']} ({r['date_range']})",
            "Current narrative state:",
        ]

        dim_short = {
            'regime_call': 'Regime',
            'risk_level': 'Risk',
            'fed_stance': 'Fed',
            'chile_positioning': 'Chile',
            'equity_conviction': 'Equity conviction',
        }

        for dim_key in self.DIMENSIONS:
            val = r['current_state'].get(dim_key, 'N/A')
            short = dim_short.get(dim_key, dim_key)
            lines.append(f"  {short}: {val}")

        recent = r.get('recent_shifts', {})
        if recent:
            lines.append("Recent shifts:")
            for dim_key, shift in recent.items():
                short = dim_short.get(dim_key, dim_key)
                lines.append(f"  {short}: {shift['from']} -> {shift['to']} (since {shift['date']})")
        else:
            lines.append("Recent shifts: None (stable narrative)")

        return "\n".join(lines)


if __name__ == "__main__":
    nt = NarrativeTracker(verbose=True)
    result = nt.run()
    print(f"\nSessions: {result['result'].get('n_sessions')}")
    print(f"Current state: {result['result'].get('current_state')}")
    print(f"Errors: {result['errors']}")
    print(f"\nCouncil input:\n{nt.get_council_input()}")
