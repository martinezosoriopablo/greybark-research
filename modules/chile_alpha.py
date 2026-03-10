# -*- coding: utf-8 -*-
"""
Greybark Research - Chile Alpha Signal Module
==============================================
Composite Chile-specific signal from 8 sub-signals scored -2 to +2.
Weighted average mapped to -100..+100 with bull/bear zones.

Usage:
    from modules.chile_alpha import ChileAlphaSignal
    ca = ChileAlphaSignal()
    result = ca.run()
"""

import json
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, Any, Optional

from .base_module import AnalyticsModuleBase, HAS_MPL

if HAS_MPL:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import yfinance as yf
except ImportError:
    yf = None


class ChileAlphaSignal(AnalyticsModuleBase):

    MODULE_NAME = "chile_alpha"

    # Sub-signal weights (sum = 1.0)
    WEIGHTS = {
        'carry':       0.15,
        'copper':      0.20,
        'imacec':      0.15,
        'spc_curve':   0.10,
        'breakeven':   0.10,
        'ipsa_vs_spy': 0.10,
        'embi':        0.10,
        'policy':      0.10,
    }

    ZONES = [
        (-100, -50, 'Strong Bear', '#c53030'),
        (-50,  -20, 'Mild Bear',   '#dd6b20'),
        (-20,   20, 'Neutral',     '#d69e2e'),
        (20,    50, 'Mild Bull',   '#276749'),
        (50,   100, 'Strong Bull', '#2b6cb0'),
    ]

    # ── Data collection ─────────────────────────────────────

    def _collect_data(self) -> Dict:
        data = {}
        data['carry'] = self._fetch_carry()
        data['copper'] = self._fetch_copper_momentum()
        data['macro'] = self._fetch_macro_snapshot()
        data['spc_curve'] = self._fetch_spc_curve()
        data['breakeven'] = self._fetch_breakeven()
        data['ipsa_vs_spy'] = self._fetch_ipsa_vs_spy()
        data['embi_prev'] = self._load_embi_state()
        return data

    def _fetch_carry(self) -> Dict:
        try:
            from greybark.analytics.chile.chile_analytics import ChileAnalytics
            ca = ChileAnalytics()
            result = ca.get_carry_trade_analysis()
            return {
                'attractiveness': result.get('assessment', {}).get('attractiveness', 'LOW'),
            }
        except Exception as e:
            self._print(f"  [ERR] Carry: {e}")
            return {'error': str(e)}

    def _fetch_copper_momentum(self) -> Dict:
        try:
            if yf is None:
                return {'error': 'yfinance not installed'}
            ticker = yf.Ticker('HG=F')
            hist = ticker.history(period='2mo')
            if hist.empty or len(hist) < 20:
                return {'error': 'Copper: insufficient data'}
            closes = hist['Close'].dropna()
            month_ago_idx = max(0, len(closes) - 22)
            ret_1m = (float(closes.iloc[-1]) / float(closes.iloc[month_ago_idx]) - 1) * 100
            return {'return_1m': round(ret_1m, 2), 'last': float(closes.iloc[-1])}
        except Exception as e:
            self._print(f"  [ERR] Copper: {e}")
            return {'error': str(e)}

    def _fetch_macro_snapshot(self) -> Dict:
        try:
            from greybark.analytics.chile.chile_analytics import ChileAnalytics
            ca = ChileAnalytics()
            snap = ca.get_macro_snapshot()
            return {
                'imacec': snap.get('imacec'),
                'embi': snap.get('embi'),
                'policy_stance': snap.get('policy_stance'),
            }
        except Exception as e:
            self._print(f"  [ERR] Macro snapshot: {e}")
            return {'error': str(e)}

    def _fetch_spc_curve(self) -> Dict:
        try:
            from greybark.analytics.chile.chile_analytics import ChileAnalytics
            ca = ChileAnalytics()
            curve = ca.get_camara_curve()
            return {'shape': curve.get('shape', 'NORMAL')}
        except Exception as e:
            self._print(f"  [ERR] SPC curve: {e}")
            return {'error': str(e)}

    def _fetch_breakeven(self) -> Dict:
        try:
            from greybark.analytics.chile.chile_analytics import ChileAnalytics
            ca = ChileAnalytics()
            be = ca.get_breakeven_inflation()
            be5y = be.get('breakevens', {}).get('5Y')
            if be5y is None:
                return {'error': 'Breakeven 5Y not available'}
            return {'be_5y': float(be5y)}
        except Exception as e:
            self._print(f"  [ERR] Breakeven: {e}")
            return {'error': str(e)}

    def _fetch_ipsa_vs_spy(self) -> Dict:
        try:
            if yf is None:
                return {'error': 'yfinance not installed'}
            ipsa = yf.Ticker('^IPSA')
            spy = yf.Ticker('SPY')
            h_ipsa = ipsa.history(period='2mo')
            h_spy = spy.history(period='2mo')
            if h_ipsa.empty or h_spy.empty or len(h_ipsa) < 20 or len(h_spy) < 20:
                return {'error': 'IPSA/SPY: insufficient data'}

            ipsa_c = h_ipsa['Close'].dropna()
            spy_c = h_spy['Close'].dropna()

            idx_ipsa = max(0, len(ipsa_c) - 22)
            idx_spy = max(0, len(spy_c) - 22)

            ipsa_ret = (float(ipsa_c.iloc[-1]) / float(ipsa_c.iloc[idx_ipsa]) - 1) * 100
            spy_ret = (float(spy_c.iloc[-1]) / float(spy_c.iloc[idx_spy]) - 1) * 100
            diff = ipsa_ret - spy_ret
            return {
                'ipsa_ret_1m': round(ipsa_ret, 2),
                'spy_ret_1m': round(spy_ret, 2),
                'diff_pp': round(diff, 2),
            }
        except Exception as e:
            self._print(f"  [ERR] IPSA vs SPY: {e}")
            return {'error': str(e)}

    # ── EMBI state persistence ──────────────────────────────

    def _load_embi_state(self) -> Optional[float]:
        path = self._output_dir / "chile_alpha_embi.json"
        if path.exists():
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                return data.get('embi')
            except Exception:
                pass
        return None

    def _save_embi_state(self, embi_val: float):
        path = self._output_dir / "chile_alpha_embi.json"
        try:
            with open(path, 'w') as f:
                json.dump({'embi': embi_val, 'timestamp': datetime.now().isoformat()}, f, indent=2)
        except Exception:
            pass

    # ── Computation ─────────────────────────────────────────

    def _compute(self) -> Dict:
        signals = {}

        # 1. Carry attractiveness (15%)
        carry = self._data.get('carry', {})
        if 'error' not in carry:
            attr = carry.get('attractiveness', 'LOW')
            score_map = {'HIGH': 2, 'MEDIUM': 1, 'LOW': 0, 'NEGATIVE': -2}
            score = score_map.get(attr, 0)
            signals['carry'] = {
                'score': score, 'raw': attr,
                'label': f"Carry: {attr}",
            }

        # 2. Copper momentum (20%)
        copper = self._data.get('copper', {})
        if 'error' not in copper:
            ret = copper.get('return_1m', 0)
            if ret > 3:
                score = 2
            elif ret > 0:
                score = 1
            elif ret < -3:
                score = -2
            else:
                score = -1
            signals['copper'] = {
                'score': score, 'raw': ret,
                'label': f"Cobre 1M: {ret:+.1f}%",
            }

        # 3. IMACEC trend (15%)
        macro = self._data.get('macro', {})
        if 'error' not in macro and macro.get('imacec') is not None:
            imacec = self._safe_float(macro['imacec'])
            if imacec > 4:
                score = 2
            elif imacec > 2:
                score = 1
            elif imacec < 0:
                score = -2
            else:
                score = 0
            signals['imacec'] = {
                'score': score, 'raw': imacec,
                'label': f"IMACEC YoY: {imacec:.1f}%",
            }

        # 4. SPC curve shape (10%)
        spc = self._data.get('spc_curve', {})
        if 'error' not in spc:
            shape = spc.get('shape', 'NORMAL')
            shape_map = {
                'STEEP': 2, 'NORMAL': 1, 'FLAT': 0,
                'INVERTED': -1, 'DEEPLY_INVERTED': -2,
            }
            score = shape_map.get(shape, 0)
            signals['spc_curve'] = {
                'score': score, 'raw': shape,
                'label': f"Curva SPC: {shape}",
            }

        # 5. Breakeven vs target (10%)
        be = self._data.get('breakeven', {})
        if 'error' not in be and be.get('be_5y') is not None:
            be5y = be['be_5y']
            deviation = abs(be5y - 3.0)
            if deviation < 0.5:
                score = 1  # near target = anchored = positive
            else:
                score = -1  # far from target = concern
            signals['breakeven'] = {
                'score': score, 'raw': be5y,
                'label': f"BE 5Y: {be5y:.2f}% (target 3%)",
            }

        # 6. IPSA vs SPY (10%)
        ipsa_spy = self._data.get('ipsa_vs_spy', {})
        if 'error' not in ipsa_spy:
            diff = ipsa_spy.get('diff_pp', 0)
            if diff > 3:
                score = 2
            elif diff > 0:
                score = 1
            elif diff < -3:
                score = -2
            else:
                score = -1
            signals['ipsa_vs_spy'] = {
                'score': score, 'raw': diff,
                'label': f"IPSA vs SPY: {diff:+.1f}pp",
            }

        # 7. EMBI direction (10%)
        embi_prev = self._data.get('embi_prev')
        embi_current = macro.get('embi') if 'error' not in macro else None
        if embi_current is not None:
            embi_val = self._safe_float(embi_current)
            if embi_prev is not None:
                if embi_val < embi_prev:
                    score = 1  # narrowing = positive
                elif embi_val > embi_prev:
                    score = -1  # widening = negative
                else:
                    score = 0
                signals['embi'] = {
                    'score': score, 'raw': embi_val,
                    'label': f"EMBI: {embi_val:.0f}bp ({'narrowing' if score > 0 else 'widening' if score < 0 else 'flat'})",
                }
            else:
                signals['embi'] = {
                    'score': 0, 'raw': embi_val,
                    'label': f"EMBI: {embi_val:.0f}bp (no prev)",
                }
            # Save for next run
            self._save_embi_state(embi_val)

        # 8. Policy stance (10%)
        if 'error' not in macro and macro.get('policy_stance'):
            stance = macro['policy_stance']
            stance_map = {'ACCOMMODATIVE': 2, 'NEUTRAL': 1, 'RESTRICTIVE': -1}
            score = stance_map.get(stance, 0)
            signals['policy'] = {
                'score': score, 'raw': stance,
                'label': f"Pol. Stance: {stance}",
            }

        # ── Composite ───────────────────────────────────────
        if signals:
            total_weight = sum(
                self.WEIGHTS.get(k, 0) for k in signals
            )
            if total_weight > 0:
                weighted = sum(
                    signals[k]['score'] * (self.WEIGHTS.get(k, 0) / total_weight)
                    for k in signals
                )
            else:
                weighted = 0.0

            # Map weighted avg (-2..+2) to -100..+100
            composite = max(-100, min(100, weighted * 50))
        else:
            composite = 0.0

        # Zone
        zone = 'Neutral'
        zone_color = '#d69e2e'
        for lo, hi, name, color in self.ZONES:
            if lo <= composite < hi or (composite == 100 and hi == 100):
                zone = name
                zone_color = color
                break

        interp = self._build_interpretation(composite, zone, signals)

        return {
            'composite_score': round(composite, 1),
            'zone': zone,
            'zone_color': zone_color,
            'signals': signals,
            'n_signals': len(signals),
            'interpretation': interp,
        }

    def _build_interpretation(self, score: float, zone: str, signals: Dict) -> str:
        tone_map = {
            'Strong Bear': "Senal fuertemente bajista para Chile. Multiples factores negativos alineados.",
            'Mild Bear': "Senal moderadamente bajista. Algunos factores pesan contra Chile.",
            'Neutral': "Senal neutral. Factores positivos y negativos se compensan.",
            'Mild Bull': "Senal moderadamente alcista. Chile muestra ventajas relativas.",
            'Strong Bull': "Senal fuertemente alcista. Chile presenta oportunidad clara de alpha.",
        }
        parts = [tone_map.get(zone, '')]

        # Top contributor
        if signals:
            best = max(signals, key=lambda k: signals[k]['score'])
            worst = min(signals, key=lambda k: signals[k]['score'])
            parts.append(
                f"Mayor contribucion positiva: {signals[best]['label']}. "
                f"Mayor lastre: {signals[worst]['label']}."
            )
        return " ".join(parts)

    # ── Chart ───────────────────────────────────────────────

    def _generate_chart(self) -> str:
        if not HAS_MPL or 'error' in self._result:
            return self._create_placeholder("Chile Alpha Signal")

        score = self._result['composite_score']
        zone = self._result['zone']
        zone_color = self._result['zone_color']
        signals = self._result.get('signals', {})

        fig, axes = plt.subplots(2, 1, figsize=(7, 5),
                                  gridspec_kw={'height_ratios': [1.2, 1]})

        # ── Top: Horizontal gauge ────────────────────────────
        ax = axes[0]
        ax.set_xlim(-110, 110)
        ax.set_ylim(-0.5, 1.5)
        ax.axis('off')

        # Draw zone bars
        for lo, hi, name, color in self.ZONES:
            width = hi - lo
            rect = mpatches.FancyBboxPatch(
                (lo, 0.3), width, 0.5,
                boxstyle="round,pad=0.02",
                facecolor=color, alpha=0.25,
                edgecolor=color, linewidth=0.8,
            )
            ax.add_patch(rect)
            mid = (lo + hi) / 2
            ax.text(mid, 0.12, name, ha='center', va='center',
                    fontsize=6.5, color=color, fontweight='bold')

        # Needle / marker
        ax.plot(score, 1.0, 'v', color=zone_color, markersize=14, zorder=5)
        ax.plot([score, score], [0.8, 1.0], color=zone_color, linewidth=2, zorder=4)
        ax.text(score, 1.25, f"{score:+.0f}", ha='center', va='center',
                fontsize=14, fontweight='bold', color=zone_color)

        ax.set_title('Chile Alpha Signal', fontsize=11, fontweight='bold',
                      color=self.COLORS['primary'], pad=8)

        # ── Bottom: Contribution bar chart ───────────────────
        ax2 = axes[1]

        if signals:
            sorted_sigs = sorted(signals.items(), key=lambda x: x[1]['score'])
            names = [s[1]['label'] for s in sorted_sigs]
            scores = [s[1]['score'] for s in sorted_sigs]
            weights = [self.WEIGHTS.get(s[0], 0) for s in sorted_sigs]
            contributions = [sc * w * 50 for sc, w in zip(scores, weights)]

            colors_bar = [
                self.COLORS['positive'] if c > 0 else
                self.COLORS['negative'] if c < 0 else
                self.COLORS['text_light']
                for c in contributions
            ]

            y_pos = range(len(names))
            ax2.barh(y_pos, contributions, color=colors_bar, height=0.6, alpha=0.85)
            ax2.set_yticks(y_pos)
            ax2.set_yticklabels(names, fontsize=7.5)
            ax2.axvline(0, color='#cbd5e0', linewidth=0.8)
            ax2.set_xlabel('Contribucion al score', fontsize=8,
                           color=self.COLORS['text_medium'])
            ax2.set_title('Descomposicion por Sub-senal', fontsize=9,
                          fontweight='bold', color=self.COLORS['primary'])

            for spine in ['top', 'right']:
                ax2.spines[spine].set_visible(False)
        else:
            ax2.text(0.5, 0.5, 'Sin datos', ha='center', va='center',
                     transform=ax2.transAxes, color=self.COLORS['text_light'])
            ax2.axis('off')

        fig.tight_layout()
        return self._fig_to_base64(fig)

    # ── Report section (HTML) ───────────────────────────────

    def get_report_section(self) -> str:
        if not self._result or 'error' in self._result:
            return '<div style="color:#718096;">Chile Alpha Signal: datos no disponibles</div>'

        r = self._result
        zone_color = r['zone_color']
        chart = self._chart or self._create_placeholder("Chile Alpha Signal")
        chart_img = f'<img src="{chart}" style="max-width:100%;"/>' if chart.startswith('data:') else chart

        # Signal rows
        rows = ''
        for key, sig in r.get('signals', {}).items():
            score = sig['score']
            icon = '+' if score > 0 else ('-' if score < 0 else '='  )
            color = self.COLORS['positive'] if score > 0 else (
                self.COLORS['negative'] if score < 0 else self.COLORS['text_medium'])
            rows += (
                f'<tr>'
                f'<td style="padding:3px 8px;font-size:11px;">{sig["label"]}</td>'
                f'<td style="padding:3px 8px;text-align:center;font-size:12px;'
                f'font-weight:700;color:{color};">{icon}{score}</td>'
                f'<td style="padding:3px 8px;text-align:right;font-size:10px;'
                f'color:{self.COLORS["text_light"]};">{self.WEIGHTS.get(key, 0):.0%}</td>'
                f'</tr>'
            )

        return (
            f'<div style="margin:20px 0;">'
            f'<div style="font-size:16px;font-weight:700;color:{self.COLORS["primary"]};'
            f'border-bottom:2px solid {self.COLORS["accent"]};padding-bottom:6px;margin-bottom:12px;">'
            f'Chile Alpha Signal</div>'
            f'<div style="text-align:center;margin:10px 0;">{chart_img}</div>'
            f'<div style="display:inline-block;padding:6px 16px;background:{zone_color};color:white;'
            f'border-radius:20px;font-size:12px;font-weight:700;margin:8px 0;">'
            f'{r["composite_score"]:+.0f} — {r["zone"]}</div>'
            f'<table style="width:100%;border-collapse:collapse;margin:10px 0;">'
            f'<tr style="border-bottom:1px solid #e2e8f0;">'
            f'<th style="text-align:left;padding:3px 8px;font-size:10px;">Sub-senal</th>'
            f'<th style="text-align:center;padding:3px 8px;font-size:10px;">Score</th>'
            f'<th style="text-align:right;padding:3px 8px;font-size:10px;">Peso</th></tr>'
            f'{rows}</table>'
            f'<p style="font-size:11px;color:#4a4a4a;margin-top:10px;line-height:1.5;">'
            f'{r["interpretation"]}</p>'
            f'</div>'
        )

    # ── Council input (plain text) ──────────────────────────

    def get_council_input(self) -> str:
        if not self._result or 'error' in self._result:
            return "[CHILE ALPHA SIGNAL MODULE] Data unavailable.\n"

        r = self._result
        lines = [
            "[CHILE ALPHA SIGNAL MODULE — Señal Alpha Chile (modelo propietario que combina múltiples indicadores para detectar oportunidades de sobre/sub-ponderación en activos chilenos; score positivo = favorable, negativo = cautela)]",
            f"Score Compuesto: {r['composite_score']:+.0f}/100 ({r['zone']})",
            f"Sub-señales ({r['n_signals']} activas):",
        ]
        for key, sig in r.get('signals', {}).items():
            arrow = '+' if sig['score'] > 0 else ('-' if sig['score'] < 0 else '=')
            lines.append(f"  {sig['label']} -> {arrow}{sig['score']} (peso {self.WEIGHTS.get(key, 0):.0%})")

        lines.append(f"Interpretación: {r['interpretation']}")
        return "\n".join(lines)


if __name__ == "__main__":
    ca = ChileAlphaSignal(verbose=True)
    result = ca.run()
    print(f"\nComposite: {result['result'].get('composite_score')}")
    print(f"Zone: {result['result'].get('zone')}")
    print(f"Errors: {result['errors']}")
    print(f"\nCouncil input:\n{ca.get_council_input()}")
