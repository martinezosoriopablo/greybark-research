# -*- coding: utf-8 -*-
"""
Greybark Research - All Weather Regime Module
==============================================
Classify environment into Dalio's 4 quadrants (Growth x Inflation).
Provides model portfolio weights and transition tracking.

Usage:
    from modules.all_weather import AllWeatherRegime
    aw = AllWeatherRegime()
    result = aw.run()
"""

import json
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List

from .base_module import AnalyticsModuleBase, HAS_MPL

if HAS_MPL:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np

try:
    import pandas as pd
except ImportError:
    pd = None


class AllWeatherRegime(AnalyticsModuleBase):

    MODULE_NAME = "all_weather"

    QUADRANTS = {
        'Q1': {
            'name': 'Goldilocks',
            'label': 'Crecimiento ↑ + Inflacion ↓',
            'growth': 'RISING', 'inflation': 'FALLING',
            'color': '#276749',
            'assets': 'Equities, Corp Bonds',
            'weights': {
                'Equities': 0.40, 'Corp Bonds': 0.25, 'Govt Bonds': 0.20,
                'Gold': 0.10, 'Cash': 0.05,
            },
        },
        'Q2': {
            'name': 'Reflation',
            'label': 'Crecimiento ↑ + Inflacion ↑',
            'growth': 'RISING', 'inflation': 'RISING',
            'color': '#dd6b20',
            'assets': 'Commodities, TIPS, EM',
            'weights': {
                'Commodities': 0.25, 'TIPS': 0.20, 'EM Equities': 0.20,
                'Gold': 0.15, 'Equities': 0.15, 'Cash': 0.05,
            },
        },
        'Q3': {
            'name': 'Deflation',
            'label': 'Crecimiento ↓ + Inflacion ↓',
            'growth': 'FALLING', 'inflation': 'FALLING',
            'color': '#2b6cb0',
            'assets': 'Govt Bonds, USD',
            'weights': {
                'Govt Bonds': 0.40, 'USD': 0.20, 'Cash': 0.20,
                'Equities': 0.10, 'Gold': 0.10,
            },
        },
        'Q4': {
            'name': 'Stagflation',
            'label': 'Crecimiento ↓ + Inflacion ↑',
            'growth': 'FALLING', 'inflation': 'RISING',
            'color': '#c53030',
            'assets': 'Gold, Commodities, Cash',
            'weights': {
                'Gold': 0.25, 'Commodities': 0.20, 'Cash': 0.20,
                'TIPS': 0.15, 'Govt Bonds': 0.15, 'Equities': 0.05,
            },
        },
    }

    # ── Data collection ─────────────────────────────────────

    def _collect_data(self) -> Dict:
        data = {
            'growth': self._fetch_growth_signals(),
            'inflation': self._fetch_inflation_signals(),
        }

        # Optional: existing regime classification for comparison
        data['regime_comparison'] = self._fetch_regime_classification()

        return data

    def _fetch_growth_signals(self) -> Dict:
        """Fetch ISM, GDP, NFP, IMACEC."""
        signals = {}

        # ISM New Orders
        try:
            from greybark.data_sources.fred_client import FREDClient
            fred = FREDClient()
            ism = fred.get_series('NEWORDER', start_date=date.today() - timedelta(days=120))
            if ism is not None and not ism.empty:
                latest = float(ism.dropna().iloc[-1])
                signals['ism_new_orders'] = {
                    'value': latest,
                    'score': 1 if latest > 50 else (-1 if latest < 48 else 0),
                    'label': f"ISM New Orders: {latest:.1f}",
                }
        except Exception as e:
            self._print(f"  [ERR] ISM: {e}")

        # GDP Real
        try:
            from greybark.data_sources.fred_client import FREDClient
            fred = FREDClient()
            gdp = fred.get_series('GDPC1', start_date=date.today() - timedelta(days=800))
            if gdp is not None and len(gdp.dropna()) >= 3:
                gdp_clean = gdp.dropna()
                latest_qoq = float(gdp_clean.pct_change().iloc[-1]) * 100
                prev_qoq = float(gdp_clean.pct_change().iloc[-2]) * 100
                accelerating = latest_qoq > prev_qoq
                signals['gdp'] = {
                    'value': round(latest_qoq, 2),
                    'score': 1 if accelerating else -1,
                    'label': f"GDP QoQ: {latest_qoq:.2f}% ({'accel' if accelerating else 'decel'})",
                }
        except Exception as e:
            self._print(f"  [ERR] GDP: {e}")

        # Nonfarm Payrolls
        try:
            from greybark.data_sources.fred_client import FREDClient
            fred = FREDClient()
            nfp = fred.get_series('PAYEMS', start_date=date.today() - timedelta(days=120))
            if nfp is not None and len(nfp.dropna()) >= 2:
                nfp_clean = nfp.dropna()
                mom_change = float(nfp_clean.diff().iloc[-1])
                signals['nfp'] = {
                    'value': round(mom_change, 0),
                    'score': 1 if mom_change > 0 else -1,
                    'label': f"NFP MoM: {mom_change:+,.0f}K",
                }
        except Exception as e:
            self._print(f"  [ERR] NFP: {e}")

        # IMACEC Chile
        try:
            from greybark.data_sources.bcch_client import BCChClient
            bcch = BCChClient()
            imacec = bcch.get_series('F032.IMC.V12.Z.Z.2018.Z.Z.0.M', days_back=120)
            if imacec is not None and not imacec.empty:
                latest = float(imacec.dropna().iloc[-1])
                signals['imacec'] = {
                    'value': round(latest, 1),
                    'score': 1 if latest > 0 else -1,
                    'label': f"IMACEC YoY: {latest:.1f}%",
                }
        except Exception as e:
            self._print(f"  [ERR] IMACEC: {e}")

        return signals

    def _fetch_inflation_signals(self) -> Dict:
        """Fetch CPI, breakevens, Core PCE."""
        signals = {}

        try:
            from greybark.data_sources.fred_client import FREDClient
            fred = FREDClient()
        except Exception as e:
            self._print(f"  [ERR] FRED init: {e}")
            return signals

        # CPI YoY
        try:
            cpi = fred.get_series('CPIAUCSL', start_date=date.today() - timedelta(days=400))
            if cpi is not None and len(cpi.dropna()) >= 13:
                cpi_clean = cpi.dropna()
                yoy = float((cpi_clean.iloc[-1] / cpi_clean.iloc[-12] - 1) * 100)
                if yoy > 3.0:
                    score = 1
                elif yoy < 2.0:
                    score = -1
                else:
                    score = 0
                signals['cpi_yoy'] = {
                    'value': round(yoy, 2),
                    'score': score,
                    'label': f"CPI YoY: {yoy:.2f}%",
                }
        except Exception as e:
            self._print(f"  [ERR] CPI: {e}")

        # Breakeven 5Y
        try:
            be5 = fred.get_series('T5YIE', start_date=date.today() - timedelta(days=120))
            if be5 is not None and len(be5.dropna()) >= 22:
                be5_clean = be5.dropna()
                current = float(be5_clean.iloc[-1])
                month_ago = float(be5_clean.iloc[-22])
                rising = current > month_ago
                signals['breakeven_5y'] = {
                    'value': round(current, 2),
                    'score': 1 if rising else -1,
                    'label': f"BE 5Y: {current:.2f}% ({'up' if rising else 'down'})",
                }
        except Exception as e:
            self._print(f"  [ERR] BE5Y: {e}")

        # Breakeven 10Y
        try:
            be10 = fred.get_series('T10YIE', start_date=date.today() - timedelta(days=120))
            if be10 is not None and len(be10.dropna()) >= 22:
                be10_clean = be10.dropna()
                current = float(be10_clean.iloc[-1])
                month_ago = float(be10_clean.iloc[-22])
                rising = current > month_ago
                signals['breakeven_10y'] = {
                    'value': round(current, 2),
                    'score': 1 if rising else -1,
                    'label': f"BE 10Y: {current:.2f}% ({'up' if rising else 'down'})",
                }
        except Exception as e:
            self._print(f"  [ERR] BE10Y: {e}")

        # Core PCE
        try:
            pce = fred.get_series('PCEPILFE', start_date=date.today() - timedelta(days=400))
            if pce is not None and len(pce.dropna()) >= 13:
                pce_clean = pce.dropna()
                yoy_now = float((pce_clean.iloc[-1] / pce_clean.iloc[-12] - 1) * 100)
                yoy_prev = float((pce_clean.iloc[-2] / pce_clean.iloc[-13] - 1) * 100)
                accelerating = yoy_now > yoy_prev
                signals['core_pce'] = {
                    'value': round(yoy_now, 2),
                    'score': 1 if accelerating else -1,
                    'label': f"Core PCE: {yoy_now:.2f}% ({'accel' if accelerating else 'decel'})",
                }
        except Exception as e:
            self._print(f"  [ERR] PCE: {e}")

        return signals

    def _fetch_regime_classification(self) -> Optional[Dict]:
        """Fetch existing regime classification for comparison."""
        try:
            from greybark.analytics.regime_classification.classifier import classify_regime
            regime = classify_regime()
            return {
                'classification': regime.get('classification', 'UNKNOWN'),
                'score': regime.get('score', 0),
            }
        except Exception as e:
            self._print(f"  [INFO] Regime classification unavailable: {e}")
            return None

    # ── Computation ─────────────────────────────────────────

    def _compute(self) -> Dict:
        growth_signals = self._data.get('growth', {})
        inflation_signals = self._data.get('inflation', {})

        # Aggregate growth
        growth_scores = [s['score'] for s in growth_signals.values()]
        growth_avg = sum(growth_scores) / len(growth_scores) if growth_scores else 0
        growth_direction = 'RISING' if growth_avg > 0 else 'FALLING'

        # Aggregate inflation
        inflation_scores = [s['score'] for s in inflation_signals.values()]
        inflation_avg = sum(inflation_scores) / len(inflation_scores) if inflation_scores else 0
        inflation_direction = 'RISING' if inflation_avg > 0 else 'FALLING'

        # Classify quadrant
        quadrant = self._classify_quadrant(growth_direction, inflation_direction)
        q_info = self.QUADRANTS[quadrant]

        # Confidence (how far from boundary)
        total_signals = len(growth_scores) + len(inflation_scores)
        if total_signals > 0:
            strength = (abs(growth_avg) + abs(inflation_avg)) / 2
            confidence = min(100, max(20, strength * 50 + 50))
        else:
            confidence = 20.0

        # Transition
        previous = self._load_previous_result()
        transition = None
        if previous and previous.get('quadrant') != quadrant:
            transition = {
                'from': previous['quadrant'],
                'from_name': self.QUADRANTS.get(previous['quadrant'], {}).get('name', '?'),
                'to': quadrant,
                'to_name': q_info['name'],
            }

        # Save current result for next run
        self._save_current_result(quadrant, growth_avg, inflation_avg)

        # Regime comparison
        regime_comp = self._data.get('regime_comparison')

        interp = self._build_interpretation(quadrant, q_info, confidence, transition)

        return {
            'quadrant': quadrant,
            'quadrant_name': q_info['name'],
            'quadrant_label': q_info['label'],
            'quadrant_color': q_info['color'],
            'growth': {
                'score': round(growth_avg, 2),
                'direction': growth_direction,
                'components': growth_signals,
            },
            'inflation': {
                'score': round(inflation_avg, 2),
                'direction': inflation_direction,
                'components': inflation_signals,
            },
            'model_weights': q_info['weights'],
            'recommended_assets': q_info['assets'],
            'confidence': round(confidence, 0),
            'transition': transition,
            'regime_comparison': regime_comp,
            'interpretation': interp,
        }

    def _classify_quadrant(self, growth: str, inflation: str) -> str:
        for qk, qv in self.QUADRANTS.items():
            if qv['growth'] == growth and qv['inflation'] == inflation:
                return qk
        return 'Q1'

    def _load_previous_result(self) -> Optional[Dict]:
        path = self._output_dir / "all_weather_last.json"
        if path.exists():
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def _save_current_result(self, quadrant: str, growth_score: float,
                             inflation_score: float):
        path = self._output_dir / "all_weather_last.json"
        try:
            data = {
                'quadrant': quadrant,
                'growth_score': growth_score,
                'inflation_score': inflation_score,
                'timestamp': datetime.now().isoformat(),
            }
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _build_interpretation(self, quadrant: str, q_info: Dict,
                              confidence: float, transition: Optional[Dict]) -> str:
        tone = {
            'Q1': "Entorno Goldilocks: crecimiento solido con inflacion contenida. Favorable para equities y corporativos.",
            'Q2': "Entorno reflacionario: crecimiento fuerte con presiones inflacionarias. Favorece commodities y activos reales.",
            'Q3': "Riesgo deflacionario: desaceleracion con inflacion cayendo. Bonos soberanos y USD como refugio.",
            'Q4': "Riesgo de stagflation: debilidad economica con inflacion persistente. Proteccion con oro y cash.",
        }
        parts = [tone.get(quadrant, '')]
        if transition:
            parts.append(
                f"TRANSICION: movimiento de {transition['from_name']} a {transition['to_name']}."
            )
        parts.append(f"Confianza: {confidence:.0f}%.")
        return " ".join(parts)

    # ── Chart: 2x2 quadrant diagram ─────────────────────────

    def _generate_chart(self) -> str:
        if not HAS_MPL or 'error' in self._result:
            return self._create_placeholder("All Weather Regime")

        quadrant = self._result['quadrant']
        growth_score = self._result['growth']['score']
        inflation_score = self._result['inflation']['score']
        transition = self._result.get('transition')

        fig, ax = plt.subplots(figsize=(6, 5))

        # Draw 4 quadrants
        quadrant_layout = {
            'Q3': (0, 0),    # bottom-left: Growth↓, Inflation↓
            'Q4': (0, 1),    # top-left: Growth↓, Inflation↑
            'Q1': (1, 0),    # bottom-right: Growth↑, Inflation↓
            'Q2': (1, 1),    # top-right: Growth↑, Inflation↑
        }

        for qk, (gx, iy) in quadrant_layout.items():
            q = self.QUADRANTS[qk]
            x0, y0 = gx * 2 - 2, iy * 2 - 2
            is_current = (qk == quadrant)
            alpha = 0.25 if is_current else 0.10
            edge_lw = 2.5 if is_current else 0.5

            rect = mpatches.FancyBboxPatch(
                (x0, y0), 2, 2,
                boxstyle="round,pad=0.05",
                facecolor=q['color'], alpha=alpha,
                edgecolor=q['color'], linewidth=edge_lw,
            )
            ax.add_patch(rect)

            # Label
            cx, cy = x0 + 1, y0 + 1.2
            ax.text(cx, cy, q['name'], ha='center', va='center',
                    fontsize=11 if is_current else 9,
                    fontweight='bold' if is_current else 'normal',
                    color=q['color'])
            ax.text(cx, cy - 0.4, q['assets'], ha='center', va='center',
                    fontsize=7, color=self.COLORS['text_medium'], style='italic')

        # Position dot
        # Map scores (-2..+2) to chart coords (-2..+2)
        dot_x = max(-1.8, min(1.8, growth_score * 1.2))
        dot_y = max(-1.8, min(1.8, inflation_score * 1.2))
        ax.plot(dot_x, dot_y, 'o', color=self.COLORS['primary'],
                markersize=14, markeredgecolor='white', markeredgewidth=2, zorder=5)
        ax.plot(dot_x, dot_y, 'o', color='white', markersize=5, zorder=6)

        # Transition arrow
        if transition:
            prev = self._load_previous_result()
            if prev:
                prev_x = max(-1.8, min(1.8, prev.get('growth_score', 0) * 1.2))
                prev_y = max(-1.8, min(1.8, prev.get('inflation_score', 0) * 1.2))
                ax.annotate('', xy=(dot_x, dot_y), xytext=(prev_x, prev_y),
                            arrowprops=dict(arrowstyle='->', color='#718096',
                                            lw=1.5, ls='--'))

        # Axes
        ax.axhline(0, color='#cbd5e0', linewidth=1, zorder=1)
        ax.axvline(0, color='#cbd5e0', linewidth=1, zorder=1)

        ax.set_xlim(-2.2, 2.2)
        ax.set_ylim(-2.2, 2.2)
        ax.set_xlabel('← Desaceleracion    Crecimiento    Expansion →',
                       fontsize=8, color=self.COLORS['text_medium'])
        ax.set_ylabel('← Desinflacion    Inflacion    Presion alcista →',
                       fontsize=8, color=self.COLORS['text_medium'])
        ax.set_title('Regimen All Weather (Dalio)', fontsize=11, fontweight='bold',
                      color=self.COLORS['primary'], pad=12)

        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)

        fig.tight_layout()
        return self._fig_to_base64(fig)

    # ── Report section (HTML) ───────────────────────────────

    def get_report_section(self) -> str:
        if not self._result or 'error' in self._result:
            return '<div style="color:#718096;">All Weather Regime: datos no disponibles</div>'

        q = self._result
        q_color = q['quadrant_color']
        chart = self._chart or self._create_placeholder("All Weather Regime")
        chart_img = f'<img src="{chart}" style="max-width:100%;"/>' if chart.startswith('data:') else chart

        # Weights table
        weight_rows = ''
        for asset, w in q['model_weights'].items():
            bar_w = w * 100
            weight_rows += (
                f'<tr>'
                f'<td style="padding:3px 8px;font-size:11px;">{asset}</td>'
                f'<td style="padding:3px 8px;font-size:11px;text-align:right;font-weight:600;">{w:.0%}</td>'
                f'<td style="padding:3px 8px;width:100px;">'
                f'<div style="background:#e2e8f0;border-radius:3px;height:8px;">'
                f'<div style="background:{q_color};width:{bar_w}%;height:8px;border-radius:3px;">'
                f'</div></div></td>'
                f'</tr>'
            )

        # Growth/Inflation signals
        def signal_html(signals: Dict) -> str:
            rows = ''
            for key, s in signals.items():
                icon = '↑' if s['score'] > 0 else ('↓' if s['score'] < 0 else '→')
                color = self.COLORS['positive'] if s['score'] > 0 else (
                    self.COLORS['negative'] if s['score'] < 0 else self.COLORS['text_medium'])
                rows += f'<div style="font-size:11px;margin:2px 0;"><span style="color:{color};font-weight:bold;">{icon}</span> {s["label"]}</div>'
            return rows

        transition_html = ''
        if q.get('transition'):
            t = q['transition']
            transition_html = (
                f'<div style="margin:8px 0;padding:8px;background:#fffff0;'
                f'border-left:3px solid #d69e2e;border-radius:4px;font-size:11px;">'
                f'TRANSICION: {t["from_name"]} → {t["to_name"]}</div>'
            )

        return (
            f'<div style="margin:20px 0;">'
            f'<div style="font-size:16px;font-weight:700;color:{self.COLORS["primary"]};'
            f'border-bottom:2px solid {self.COLORS["accent"]};padding-bottom:6px;margin-bottom:12px;">'
            f'Regimen All Weather (Dalio)</div>'
            f'<div style="text-align:center;margin:10px 0;">{chart_img}</div>'
            f'<div style="display:inline-block;padding:6px 16px;background:{q_color};color:white;'
            f'border-radius:20px;font-size:12px;font-weight:700;margin:8px 0;">'
            f'{q["quadrant"]} — {q["quadrant_name"]} | Confianza: {q["confidence"]:.0f}%</div>'
            f'{transition_html}'
            f'<div style="display:flex;gap:20px;margin:12px 0;">'
            f'<div style="flex:1;"><div style="font-size:11px;font-weight:700;margin-bottom:4px;">Crecimiento ({q["growth"]["direction"]})</div>'
            f'{signal_html(q["growth"]["components"])}</div>'
            f'<div style="flex:1;"><div style="font-size:11px;font-weight:700;margin-bottom:4px;">Inflacion ({q["inflation"]["direction"]})</div>'
            f'{signal_html(q["inflation"]["components"])}</div></div>'
            f'<div style="margin:12px 0;"><div style="font-size:12px;font-weight:700;margin-bottom:6px;">Portafolio Modelo</div>'
            f'<table style="width:100%;border-collapse:collapse;">{weight_rows}</table></div>'
            f'<p style="font-size:11px;color:#4a4a4a;line-height:1.5;">{q["interpretation"]}</p>'
            f'</div>'
        )

    # ── Council input (plain text) ──────────────────────────

    def get_council_input(self) -> str:
        if not self._result or 'error' in self._result:
            return "[ALL WEATHER REGIME MODULE] Data unavailable.\n"

        q = self._result
        lines = [
            "[ALL WEATHER REGIME MODULE]",
            f"Current Quadrant: {q['quadrant']} - {q['quadrant_name']} ({q['quadrant_label']})",
            f"Confidence: {q['confidence']:.0f}%",
            "",
            f"Growth signals (direction: {q['growth']['direction']}, avg score: {q['growth']['score']:.2f}):",
        ]
        for key, s in q['growth']['components'].items():
            arrow = '+' if s['score'] > 0 else ('-' if s['score'] < 0 else '=')
            lines.append(f"  {s['label']} -> {arrow}{s['score']}")

        lines.append(f"\nInflation signals (direction: {q['inflation']['direction']}, avg score: {q['inflation']['score']:.2f}):")
        for key, s in q['inflation']['components'].items():
            arrow = '+' if s['score'] > 0 else ('-' if s['score'] < 0 else '=')
            lines.append(f"  {s['label']} -> {arrow}{s['score']}")

        lines.append(f"\nRecommended model weights:")
        for asset, w in q['model_weights'].items():
            lines.append(f"  {asset}: {w:.0%}")

        if q.get('transition'):
            t = q['transition']
            lines.append(f"\nTRANSITION: {t['from_name']} -> {t['to_name']}")
        else:
            lines.append(f"\nTransition: Stable (same quadrant)")

        if q.get('regime_comparison'):
            rc = q['regime_comparison']
            lines.append(f"\nRegime classifier comparison: {rc['classification']} (score: {rc['score']:.2f})")

        lines.append(f"\nInterpretation: {q['interpretation']}")
        return "\n".join(lines)


if __name__ == "__main__":
    aw = AllWeatherRegime(verbose=True)
    result = aw.run()
    print(f"\nQuadrant: {result['result'].get('quadrant')} - {result['result'].get('quadrant_name')}")
    print(f"Confidence: {result['result'].get('confidence')}")
    print(f"Errors: {result['errors']}")
    print(f"\nCouncil input:\n{aw.get_council_input()}")
