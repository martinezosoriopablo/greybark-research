# -*- coding: utf-8 -*-
"""
Greybark Research - Market Breadth & Internals Module
=====================================================
Composite 0-100 breadth score from 4 sub-signals wrapping MarketBreadthAnalytics.
Helps RV agent detect narrow vs broad rallies.

Usage:
    from modules.breadth_internals import BreadthInternals
    bi = BreadthInternals()
    result = bi.run()
    html = bi.get_report_section()
    text = bi.get_council_input()
"""

from typing import Dict, Any, List, Tuple

from .base_module import AnalyticsModuleBase, HAS_MPL

if HAS_MPL:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np


class BreadthInternals(AnalyticsModuleBase):

    MODULE_NAME = "breadth_internals"

    WEIGHTS = {
        'sector_breadth': 0.30,
        'risk_appetite': 0.25,
        'cyclical_defensive': 0.25,
        'size_factor': 0.20,
    }

    ZONES: List[Tuple[float, float, str, str]] = [
        (0,  20, 'Very Weak',   '#c53030'),
        (20, 40, 'Weak',        '#dd6b20'),
        (40, 60, 'Mixed',       '#d69e2e'),
        (60, 80, 'Healthy',     '#276749'),
        (80, 100, 'Very Strong', '#2b6cb0'),
    ]

    # ── Data collection ─────────────────────────────────────

    def _collect_data(self) -> Dict:
        from greybark.analytics.breadth.market_breadth import MarketBreadthAnalytics
        mba = MarketBreadthAnalytics()

        data = {}

        # 1. Sector breadth
        try:
            data['sector_breadth'] = mba.get_sector_breadth()
        except Exception as e:
            self._print(f"  [ERR] Sector breadth: {e}")
            data['sector_breadth'] = {'error': str(e)}

        # 2. Risk appetite
        try:
            data['risk_appetite'] = mba.get_risk_appetite_indicator()
        except Exception as e:
            self._print(f"  [ERR] Risk appetite: {e}")
            data['risk_appetite'] = {'error': str(e)}

        # 3. Cyclical / Defensive ratio
        try:
            data['cyclical_defensive'] = mba.get_cyclical_defensive_ratio()
        except Exception as e:
            self._print(f"  [ERR] Cyclical/Defensive: {e}")
            data['cyclical_defensive'] = {'error': str(e)}

        # 4. Size factor
        try:
            data['size_factor'] = mba.get_size_factor_signal()
        except Exception as e:
            self._print(f"  [ERR] Size factor: {e}")
            data['size_factor'] = {'error': str(e)}

        return data

    # ── Computation ─────────────────────────────────────────

    def _compute(self) -> Dict:
        signals = {}

        # 1. Sector breadth → pct_above_50ma
        sb = self._data.get('sector_breadth', {})
        if 'error' not in sb:
            pct = sb.get('metrics', {}).get('pct_above_50ma', 50.0)
            if pct > 80:
                score = 2
            elif pct > 60:
                score = 1
            elif pct < 20:
                score = -2
            elif pct < 40:
                score = -1
            else:
                score = 0
            signals['sector_breadth'] = {
                'score': score,
                'raw': pct,
                'label': f"Sectors above 50MA: {pct:.0f}%",
            }

        # 2. Risk appetite → signal string
        ra = self._data.get('risk_appetite', {})
        if 'error' not in ra:
            sig = ra.get('signal', 'NEUTRAL')
            score_map = {
                'STRONG_RISK_ON': 2, 'RISK_ON': 1, 'NEUTRAL': 0,
                'RISK_OFF': -1, 'STRONG_RISK_OFF': -2,
            }
            score = score_map.get(sig, 0)
            signals['risk_appetite'] = {
                'score': score,
                'raw': sig,
                'label': f"Risk appetite: {sig}",
            }

        # 3. Cyclical / Defensive → signal + cycle_position
        cd = self._data.get('cyclical_defensive', {})
        if 'error' not in cd:
            sig = cd.get('signal', 'SLIGHT_CYCLICAL')
            score_map = {
                'CYCLICAL_LEADERSHIP': 2, 'SLIGHT_CYCLICAL': 1,
                'SLIGHT_DEFENSIVE': -1, 'DEFENSIVE_LEADERSHIP': -2,
            }
            score = score_map.get(sig, 0)
            cycle = cd.get('cycle_position', '')
            signals['cyclical_defensive'] = {
                'score': score,
                'raw': sig,
                'label': f"Cycle: {sig}",
                'cycle_position': cycle,
            }

        # 4. Size factor → IWM vs SPY 1M spread
        sf = self._data.get('size_factor', {})
        if 'error' not in sf:
            periods = sf.get('periods', {})
            spread_1m = periods.get('1M', {}).get('spread', 0.0)
            if spread_1m > 3:
                score = 2
            elif spread_1m > 0:
                score = 1
            elif spread_1m < -3:
                score = -2
            else:
                score = -1
            leader = periods.get('1M', {}).get('leader', 'SPY')
            signals['size_factor'] = {
                'score': score,
                'raw': spread_1m,
                'label': f"Size: {leader} leads by {abs(spread_1m):.1f}pp",
            }

        # ── Composite: weighted avg of scores (-2..+2) → 0..100
        if signals:
            total_w = sum(self.WEIGHTS.get(k, 0) for k in signals)
            if total_w > 0:
                weighted_avg = sum(
                    signals[k]['score'] * (self.WEIGHTS.get(k, 0) / total_w)
                    for k in signals
                )
            else:
                weighted_avg = 0.0
            # Map -2..+2 → 0..100
            breadth_score = max(0.0, min(100.0, (weighted_avg + 2) / 4 * 100))
        else:
            breadth_score = 50.0

        # Zone
        zone = 'Mixed'
        zone_color = '#d69e2e'
        for lo, hi, name, color in self.ZONES:
            if lo <= breadth_score < hi or (hi == 100 and breadth_score == 100):
                zone = name
                zone_color = color
                break

        # Sector detail for council input
        sectors_data = sb.get('sectors', {}) if 'error' not in sb else {}
        sector_returns = {}
        for etf, info in sectors_data.items():
            ret_1m = info.get('returns', {}).get('1M', 0.0)
            sector_returns[etf] = ret_1m

        sorted_sectors = sorted(sector_returns.items(), key=lambda x: x[1], reverse=True)
        top_sectors = sorted_sectors[:3] if sorted_sectors else []
        lagging_sectors = sorted_sectors[-3:] if len(sorted_sectors) >= 3 else []

        n_above = sb.get('metrics', {}).get('sectors_above_50ma', 0) if 'error' not in sb else 0
        total_sectors = sb.get('metrics', {}).get('total_sectors', 11) if 'error' not in sb else 11

        interp = self._build_interpretation(breadth_score, zone, signals)

        return {
            'breadth_score': round(breadth_score, 1),
            'zone': zone,
            'zone_color': zone_color,
            'signals': signals,
            'n_signals': len(signals),
            'sectors_above_50ma': n_above,
            'total_sectors': total_sectors,
            'sector_returns': sector_returns,
            'top_sectors': top_sectors,
            'lagging_sectors': lagging_sectors,
            'cyclical_avg': cd.get('cyclical_avg_return', 0.0) if 'error' not in cd else 0.0,
            'defensive_avg': cd.get('defensive_avg_return', 0.0) if 'error' not in cd else 0.0,
            'cycle_position': cd.get('cycle_position', '') if 'error' not in cd else '',
            'interpretation': interp,
        }

    def _build_interpretation(self, score: float, zone: str, signals: Dict) -> str:
        tone_map = {
            'Very Weak': "Market breadth extremely weak — narrow participation, risk-off dominant.",
            'Weak': "Breadth deteriorating — fewer sectors participating in rally.",
            'Mixed': "Breadth mixed — no clear signal from internals.",
            'Healthy': "Breadth healthy — broad participation across sectors.",
            'Very Strong': "Breadth very strong — wide participation, risk-on dominant.",
        }
        parts = [tone_map.get(zone, '')]
        if signals:
            best = max(signals, key=lambda k: signals[k]['score'])
            worst = min(signals, key=lambda k: signals[k]['score'])
            parts.append(
                f"Strongest signal: {signals[best]['label']}. "
                f"Weakest: {signals[worst]['label']}."
            )
        return " ".join(parts)

    # ── Chart ───────────────────────────────────────────────

    def _generate_chart(self) -> str:
        if not HAS_MPL or 'error' in self._result:
            return self._create_placeholder("Market Breadth & Internals")

        sector_returns = self._result.get('sector_returns', {})
        signals = self._result.get('signals', {})
        sectors_data = self._data.get('sector_breadth', {}).get('sectors', {})

        fig, axes = plt.subplots(2, 1, figsize=(8, 5.5),
                                  gridspec_kw={'height_ratios': [1.3, 1]})

        # ── Top: Sector heatmap (horizontal bars colored by 1M return) ──
        ax = axes[0]
        if sector_returns:
            sorted_etfs = sorted(sector_returns.items(), key=lambda x: x[1])
            etfs = [s[0] for s in sorted_etfs]
            rets = [s[1] for s in sorted_etfs]

            colors = []
            for r in rets:
                if r > 0:
                    intensity = min(1.0, abs(r) / 8.0)
                    colors.append((0.15, 0.4 + 0.4 * intensity, 0.29, 0.7 + 0.3 * intensity))
                else:
                    intensity = min(1.0, abs(r) / 8.0)
                    colors.append((0.77, 0.19, 0.19, 0.5 + 0.5 * intensity))

            y_pos = range(len(etfs))
            ax.barh(y_pos, rets, color=colors, height=0.65, alpha=0.9)
            ax.set_yticks(y_pos)
            ax.set_yticklabels(etfs, fontsize=8)
            ax.axvline(0, color='#cbd5e0', linewidth=0.8)

            # 50MA dot indicator
            for i, etf in enumerate(etfs):
                info = sectors_data.get(etf, {})
                above = info.get('above_50ma', None)
                if above is not None:
                    dot_color = self.COLORS['positive'] if above else self.COLORS['negative']
                    ax.plot(rets[i], i, 'o', color=dot_color, markersize=5, zorder=5)

            ax.set_xlabel('1M Return (%)', fontsize=8, color=self.COLORS['text_medium'])
            ax.set_title('Sector Returns (1M) with 50MA Status', fontsize=10,
                          fontweight='bold', color=self.COLORS['primary'])
        else:
            ax.text(0.5, 0.5, 'No sector data', ha='center', va='center',
                     transform=ax.transAxes, color=self.COLORS['text_light'])
            ax.axis('off')

        # ── Bottom: 4 signal bars ──
        ax2 = axes[1]
        if signals:
            sig_names = list(signals.keys())
            sig_labels = [signals[k]['label'] for k in sig_names]
            sig_scores = [signals[k]['score'] for k in sig_names]

            colors_bar = []
            for s in sig_scores:
                if s > 0:
                    colors_bar.append(self.COLORS['positive'])
                elif s < 0:
                    colors_bar.append(self.COLORS['negative'])
                else:
                    colors_bar.append(self.COLORS['text_light'])

            y_pos = range(len(sig_labels))
            ax2.barh(y_pos, sig_scores, color=colors_bar, height=0.55, alpha=0.85)
            ax2.set_yticks(y_pos)
            ax2.set_yticklabels(sig_labels, fontsize=7.5)
            ax2.set_xlim(-2.5, 2.5)
            ax2.axvline(0, color='#cbd5e0', linewidth=0.8)

            for i, s in enumerate(sig_scores):
                ax2.text(s + (0.1 if s >= 0 else -0.1), i,
                         f"{s:+d}", ha='left' if s >= 0 else 'right',
                         va='center', fontsize=8, fontweight='bold',
                         color=colors_bar[i])

            ax2.set_xlabel('Score (-2 to +2)', fontsize=8, color=self.COLORS['text_medium'])
            ax2.set_title('Sub-Signal Scores', fontsize=10,
                          fontweight='bold', color=self.COLORS['primary'])
            for spine in ['top', 'right']:
                ax2.spines[spine].set_visible(False)
        else:
            ax2.text(0.5, 0.5, 'No signal data', ha='center', va='center',
                     transform=ax2.transAxes, color=self.COLORS['text_light'])
            ax2.axis('off')

        fig.tight_layout()
        return self._fig_to_base64(fig)

    # ── Report section (HTML) ───────────────────────────────

    def get_report_section(self) -> str:
        if not self._result or 'error' in self._result:
            return '<div style="color:#718096;">Market Breadth: datos no disponibles</div>'

        r = self._result
        zone_color = r['zone_color']
        chart = self._chart or self._create_placeholder("Market Breadth & Internals")
        chart_img = f'<img src="{chart}" style="max-width:100%;"/>' if chart.startswith('data:') else chart

        # Signal rows
        rows = ''
        for key, sig in r.get('signals', {}).items():
            score = sig['score']
            color = (self.COLORS['positive'] if score > 0 else
                     self.COLORS['negative'] if score < 0 else
                     self.COLORS['text_medium'])
            rows += (
                f'<tr>'
                f'<td style="padding:3px 8px;font-size:11px;">{sig["label"]}</td>'
                f'<td style="padding:3px 8px;text-align:center;font-size:12px;'
                f'font-weight:700;color:{color};">{score:+d}</td>'
                f'<td style="padding:3px 8px;text-align:right;font-size:10px;'
                f'color:{self.COLORS["text_light"]};">{self.WEIGHTS.get(key, 0):.0%}</td>'
                f'</tr>'
            )

        return (
            f'<div style="margin:20px 0;">'
            f'<div style="font-size:16px;font-weight:700;color:{self.COLORS["primary"]};'
            f'border-bottom:2px solid {self.COLORS["accent"]};padding-bottom:6px;margin-bottom:12px;">'
            f'Market Breadth & Internals</div>'
            f'<div style="text-align:center;margin:10px 0;">{chart_img}</div>'
            f'<div style="display:inline-block;padding:6px 16px;background:{zone_color};color:white;'
            f'border-radius:20px;font-size:12px;font-weight:700;margin:8px 0;">'
            f'{r["breadth_score"]:.0f}/100 — {r["zone"]}</div>'
            f'<table style="width:100%;border-collapse:collapse;margin:10px 0;">'
            f'<tr style="border-bottom:1px solid #e2e8f0;">'
            f'<th style="text-align:left;padding:3px 8px;font-size:10px;">Sub-signal</th>'
            f'<th style="text-align:center;padding:3px 8px;font-size:10px;">Score</th>'
            f'<th style="text-align:right;padding:3px 8px;font-size:10px;">Weight</th></tr>'
            f'{rows}</table>'
            f'<p style="font-size:11px;color:#4a4a4a;margin-top:10px;line-height:1.5;">'
            f'{r["interpretation"]}</p>'
            f'</div>'
        )

    # ── Council input (plain text) ──────────────────────────

    def get_council_input(self) -> str:
        if not self._result or 'error' in self._result:
            return "[MARKET BREADTH MODULE] Data unavailable.\n"

        r = self._result
        n_above = r.get('sectors_above_50ma', 0)
        total = r.get('total_sectors', 11)
        pct = (n_above / total * 100) if total else 0

        ra_sig = r.get('signals', {}).get('risk_appetite', {})
        ra_label = ra_sig.get('raw', 'N/A') if ra_sig else 'N/A'
        cyc_avg = r.get('cyclical_avg', 0)
        def_avg = r.get('defensive_avg', 0)
        cycle_pos = r.get('cycle_position', 'N/A')

        sf_sig = r.get('signals', {}).get('size_factor', {})
        sf_label = sf_sig.get('label', 'N/A') if sf_sig else 'N/A'

        top = r.get('top_sectors', [])
        lag = r.get('lagging_sectors', [])

        lines = [
            "[MARKET BREADTH MODULE]",
            f"Breadth Score: {r['breadth_score']:.0f}/100 ({r['zone']})",
            f"Sectors above 50MA: {n_above}/{total} ({pct:.1f}%)",
            f"Risk appetite: {ra_label} (cyclical {cyc_avg:+.1f}% vs defensive {def_avg:+.1f}%)",
            f"Cycle position: {cycle_pos}",
            f"{sf_label}",
        ]

        if top:
            top_str = ", ".join(f"{etf} {ret:+.1f}%" for etf, ret in top)
            lines.append(f"Top sectors: {top_str}")
        if lag:
            lag_str = ", ".join(f"{etf} {ret:+.1f}%" for etf, ret in lag)
            lines.append(f"Lagging: {lag_str}")

        return "\n".join(lines)


if __name__ == "__main__":
    bi = BreadthInternals(verbose=True)
    result = bi.run()
    print(f"\nBreadth Score: {result['result'].get('breadth_score')}")
    print(f"Zone: {result['result'].get('zone')}")
    print(f"Errors: {result['errors']}")
    print(f"\nCouncil input:\n{bi.get_council_input()}")
