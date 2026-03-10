# -*- coding: utf-8 -*-
"""
Greybark Research - Credit Risk Monitor Module
===============================================
Wraps CreditSpreadAnalytics to provide IG/HY breakdowns by rating,
quality rotation signals, and a composite stress score 0-100.
Helps RF + Risk agents see quality rotation and compression/decompression.

Usage:
    from modules.credit_risk_monitor import CreditRiskMonitor
    cr = CreditRiskMonitor()
    result = cr.run()
    html = cr.get_report_section()
    text = cr.get_council_input()
"""

from typing import Dict, Any, List, Tuple

from .base_module import AnalyticsModuleBase, HAS_MPL

if HAS_MPL:
    import matplotlib.pyplot as plt
    import numpy as np


class CreditRiskMonitor(AnalyticsModuleBase):

    MODULE_NAME = "credit_risk_monitor"

    STRESS_ZONES: List[Tuple[float, float, str, str]] = [
        (0,  30, 'LOW',      '#276749'),
        (30, 60, 'MODERATE', '#d69e2e'),
        (60, 80, 'ELEVATED', '#dd6b20'),
        (80, 100, 'CRITICAL', '#c53030'),
    ]

    IG_RATINGS = ['aaa', 'aa', 'a', 'bbb']
    HY_RATINGS = ['bb', 'b', 'ccc']

    # ── Data collection ─────────────────────────────────────

    def _collect_data(self) -> Dict:
        from greybark.analytics.credit.credit_spreads import CreditSpreadAnalytics
        csa = CreditSpreadAnalytics()

        data = {}

        # 1. IG breakdown
        try:
            data['ig'] = csa.get_ig_breakdown()
        except Exception as e:
            self._print(f"  [ERR] IG breakdown: {e}")
            data['ig'] = {'error': str(e)}

        # 2. HY breakdown
        try:
            data['hy'] = csa.get_hy_breakdown()
        except Exception as e:
            self._print(f"  [ERR] HY breakdown: {e}")
            data['hy'] = {'error': str(e)}

        # 3. Quality rotation signal
        try:
            data['quality'] = csa.get_quality_rotation_signal()
        except Exception as e:
            self._print(f"  [ERR] Quality rotation: {e}")
            data['quality'] = {'error': str(e)}

        return data

    # ── Computation ─────────────────────────────────────────

    def _compute(self) -> Dict:
        ig = self._data.get('ig', {})
        hy = self._data.get('hy', {})
        quality = self._data.get('quality', {})

        # ── IG regime ──
        ig_total = ig.get('total', {}) if 'error' not in ig else {}
        ig_bps = self._safe_float(ig_total.get('current_bps'))
        ig_pctl = self._safe_float(ig_total.get('percentile_5y'))
        ig_level = ig_total.get('level', 'normal').upper()
        ig_signal = ig_total.get('signal', '')

        # Per-rating IG details
        ig_ratings = {}
        if 'error' not in ig:
            for rating in self.IG_RATINGS:
                rd = ig.get(rating, {})
                if rd:
                    ig_ratings[rating.upper()] = {
                        'bps': self._safe_float(rd.get('current_bps')),
                        'pctl': self._safe_float(rd.get('percentile_5y')),
                        'level': rd.get('level', 'normal').upper(),
                        'momentum_1m': self._safe_float(rd.get('momentum_1m_bps')),
                    }

        # ── HY regime ──
        hy_total = hy.get('total', {}) if 'error' not in hy else {}
        hy_bps = self._safe_float(hy_total.get('current_bps'))
        hy_pctl = self._safe_float(hy_total.get('percentile_5y'))
        hy_level = hy_total.get('level', 'normal').upper()
        hy_signal = hy_total.get('signal', '')

        # Per-rating HY details
        hy_ratings = {}
        if 'error' not in hy:
            for rating in self.HY_RATINGS:
                rd = hy.get(rating, {})
                if rd:
                    hy_ratings[rating.upper()] = {
                        'bps': self._safe_float(rd.get('current_bps')),
                        'pctl': self._safe_float(rd.get('percentile_5y')),
                        'level': rd.get('level', 'normal').upper(),
                        'momentum_1m': self._safe_float(rd.get('momentum_1m_bps')),
                    }

        # ── Quality rotation ──
        quality_signal = 'NEUTRAL'
        quality_rationale = ''
        quality_ratios = {}
        if 'error' not in quality:
            rec = quality.get('recommendation', 'NEUTRAL')
            signal_map = {
                'UP_IN_QUALITY': 'UP',
                'DOWN_IN_QUALITY': 'DOWN',
                'NEUTRAL': 'NEUTRAL',
            }
            quality_signal = signal_map.get(rec, 'NEUTRAL')
            quality_rationale = quality.get('rationale', '')
            ratios_raw = quality.get('ratios', {})
            for ratio_key in ('bbb_a_ratio', 'b_bb_ratio', 'hy_ig_ratio'):
                rd = ratios_raw.get(ratio_key, {})
                if rd:
                    quality_ratios[ratio_key] = {
                        'current': self._safe_float(rd.get('current')),
                        'percentile': self._safe_float(rd.get('percentile')),
                        'interpretation': rd.get('interpretation', ''),
                    }

        # ── Stress score 0-100 ──
        # Weighted: IG pctl (30%), HY pctl (30%), CCC pctl (20%), quality ratio avg (20%)
        ccc_pctl = hy_ratings.get('CCC', {}).get('pctl', 50.0)

        # Quality ratio component: avg percentile of ratios
        ratio_pctls = [r.get('percentile', 50.0) for r in quality_ratios.values()]
        ratio_avg_pctl = sum(ratio_pctls) / len(ratio_pctls) if ratio_pctls else 50.0

        stress_score = (
            ig_pctl * 0.30 +
            hy_pctl * 0.30 +
            ccc_pctl * 0.20 +
            ratio_avg_pctl * 0.20
        )
        stress_score = max(0.0, min(100.0, stress_score))

        # Stress zone
        stress_zone = 'MODERATE'
        zone_color = '#d69e2e'
        for lo, hi, name, color in self.STRESS_ZONES:
            if lo <= stress_score < hi or (hi == 100 and stress_score == 100):
                stress_zone = name
                zone_color = color
                break

        # ── Widening alerts: ratings with 1M momentum > +20bp ──
        widening_alerts = []
        for rating, info in {**ig_ratings, **hy_ratings}.items():
            mom = info.get('momentum_1m', 0)
            if mom > 20:
                widening_alerts.append(f"{rating} +{mom:.0f}bp")

        interp = self._build_interpretation(
            stress_score, stress_zone, ig_level, hy_level,
            quality_signal, widening_alerts, ig_bps, hy_bps)

        return {
            'stress_score': round(stress_score, 1),
            'stress_zone': stress_zone,
            'zone_color': zone_color,
            'ig_regime': ig_level,
            'ig_bps': ig_bps,
            'ig_pctl': ig_pctl,
            'ig_signal': ig_signal,
            'ig_ratings': ig_ratings,
            'hy_regime': hy_level,
            'hy_bps': hy_bps,
            'hy_pctl': hy_pctl,
            'hy_signal': hy_signal,
            'hy_ratings': hy_ratings,
            'quality_signal': quality_signal,
            'quality_rationale': quality_rationale,
            'quality_ratios': quality_ratios,
            'widening_alerts': widening_alerts,
            'interpretation': interp,
        }

    def _build_interpretation(self, score: float, zone: str,
                              ig_level: str, hy_level: str,
                              quality: str, alerts: list,
                              ig_bps: float, hy_bps: float) -> str:
        parts = []
        zone_desc = {
            'LOW': "Credit stress low — spreads compressed, benign conditions.",
            'MODERATE': "Credit stress moderate — spreads near historical norms.",
            'ELEVATED': "Credit stress elevated — spreads widening, risk repricing.",
            'CRITICAL': "Credit stress critical — spreads at crisis levels, significant risk.",
        }
        parts.append(zone_desc.get(zone, ''))

        if ig_level == 'TIGHT' and hy_level == 'TIGHT':
            parts.append("Spreads very compressed — low carry compensation for credit risk.")
        elif ig_level == 'WIDE' or hy_level == 'WIDE':
            parts.append("Spread widening signals credit deterioration.")

        if quality == 'UP':
            parts.append("Quality rotation: move UP in quality (risk-off signal).")
        elif quality == 'DOWN':
            parts.append("Quality rotation: move DOWN in quality (reach for yield).")

        if alerts:
            parts.append(f"Widening alerts: {', '.join(alerts)}.")

        return " ".join(parts)

    # ── Chart ───────────────────────────────────────────────

    def _generate_chart(self) -> str:
        if not HAS_MPL or 'error' in self._result:
            return self._create_placeholder("Credit Risk Monitor")

        r = self._result
        ig_ratings = r.get('ig_ratings', {})
        hy_ratings = r.get('hy_ratings', {})
        quality_ratios = r.get('quality_ratios', {})

        fig, axes = plt.subplots(2, 1, figsize=(8, 5.5),
                                  gridspec_kw={'height_ratios': [1.3, 1]})

        # ── Top: All ratings spread bars ──
        ax = axes[0]
        all_ratings = {}
        for rating in ['AAA', 'AA', 'A', 'BBB']:
            if rating in ig_ratings:
                all_ratings[rating] = ig_ratings[rating]
        for rating in ['BB', 'B', 'CCC']:
            if rating in hy_ratings:
                all_ratings[rating] = hy_ratings[rating]

        if all_ratings:
            labels = list(all_ratings.keys())
            bps_vals = [all_ratings[k]['bps'] for k in labels]
            pctls = [all_ratings[k]['pctl'] for k in labels]
            levels = [all_ratings[k]['level'] for k in labels]

            level_colors = {
                'TIGHT': self.COLORS['positive'],
                'NORMAL': '#d69e2e',
                'WIDE': self.COLORS['accent'],
                'CRISIS': self.COLORS['negative'],
            }
            colors = [level_colors.get(lv, '#718096') for lv in levels]

            y_pos = np.arange(len(labels))
            bars = ax.barh(y_pos, bps_vals, color=colors, height=0.55, alpha=0.85)

            # Percentile annotations
            for i, (bps, pctl) in enumerate(zip(bps_vals, pctls)):
                ax.text(bps + max(bps_vals) * 0.02, i,
                        f'{bps:.0f}bp ({pctl:.0f}th pctl)',
                        ha='left', va='center', fontsize=7.5, fontweight='bold')

            ax.set_yticks(y_pos)
            ax.set_yticklabels(labels, fontsize=9, fontweight='bold')
            ax.set_xlabel('Spread (bps)', fontsize=8, color=self.COLORS['text_medium'])
            ax.set_title('Credit Spreads by Rating', fontsize=10,
                          fontweight='bold', color=self.COLORS['primary'])

            # Add IG/HY separator
            ig_count = sum(1 for r in labels if r in ('AAA', 'AA', 'A', 'BBB'))
            if 0 < ig_count < len(labels):
                ax.axhline(ig_count - 0.5, color='#cbd5e0', linewidth=1.0,
                           linestyle='--', alpha=0.7)
                ax.text(max(bps_vals) * 0.9, ig_count - 0.7, 'IG',
                        fontsize=7, color=self.COLORS['text_light'], ha='right')
                ax.text(max(bps_vals) * 0.9, ig_count - 0.3, 'HY',
                        fontsize=7, color=self.COLORS['text_light'], ha='right')

            for spine in ['top', 'right']:
                ax.spines[spine].set_visible(False)
        else:
            ax.text(0.5, 0.5, 'No spread data', ha='center', va='center',
                     transform=ax.transAxes, color=self.COLORS['text_light'])
            ax.axis('off')

        # ── Bottom: Quality rotation ratios ──
        ax2 = axes[1]
        ratio_labels_map = {
            'bbb_a_ratio': 'BBB/A',
            'b_bb_ratio': 'B/BB',
            'hy_ig_ratio': 'HY/IG',
        }

        if quality_ratios:
            labels_q = []
            values_q = []
            pctls_q = []
            for key in ('bbb_a_ratio', 'b_bb_ratio', 'hy_ig_ratio'):
                if key in quality_ratios:
                    labels_q.append(ratio_labels_map.get(key, key))
                    values_q.append(quality_ratios[key]['current'])
                    pctls_q.append(quality_ratios[key]['percentile'])

            if labels_q:
                y_pos = np.arange(len(labels_q))
                pctl_colors = []
                for p in pctls_q:
                    if p > 70:
                        pctl_colors.append(self.COLORS['negative'])
                    elif p > 40:
                        pctl_colors.append('#d69e2e')
                    else:
                        pctl_colors.append(self.COLORS['positive'])

                ax2.barh(y_pos, values_q, color=pctl_colors, height=0.45, alpha=0.85)
                ax2.set_yticks(y_pos)
                ax2.set_yticklabels(labels_q, fontsize=9, fontweight='bold')

                for i, (v, p) in enumerate(zip(values_q, pctls_q)):
                    ax2.text(v + max(values_q) * 0.02, i,
                             f'{v:.2f}x ({p:.0f}th pctl)',
                             ha='left', va='center', fontsize=7.5)

                ax2.set_xlabel('Ratio', fontsize=8, color=self.COLORS['text_medium'])
                ax2.set_title(f'Quality Rotation — Signal: {r.get("quality_signal", "N/A")}',
                              fontsize=10, fontweight='bold', color=self.COLORS['primary'])
                for spine in ['top', 'right']:
                    ax2.spines[spine].set_visible(False)
            else:
                ax2.text(0.5, 0.5, 'No ratio data', ha='center', va='center',
                         transform=ax2.transAxes, color=self.COLORS['text_light'])
                ax2.axis('off')
        else:
            ax2.text(0.5, 0.5, 'No quality rotation data', ha='center', va='center',
                     transform=ax2.transAxes, color=self.COLORS['text_light'])
            ax2.axis('off')

        fig.tight_layout()
        return self._fig_to_base64(fig)

    # ── Report section (HTML) ───────────────────────────────

    def get_report_section(self) -> str:
        if not self._result or 'error' in self._result:
            return '<div style="color:#718096;">Credit Risk Monitor: datos no disponibles</div>'

        r = self._result
        zone_color = r['zone_color']
        chart = self._chart or self._create_placeholder("Credit Risk Monitor")
        chart_img = f'<img src="{chart}" style="max-width:100%;"/>' if chart.startswith('data:') else chart

        # Rating rows
        rows = ''
        for rating, info in {**r.get('ig_ratings', {}), **r.get('hy_ratings', {})}.items():
            level = info.get('level', '')
            level_color = {
                'TIGHT': self.COLORS['positive'], 'NORMAL': '#d69e2e',
                'WIDE': self.COLORS['accent'], 'CRISIS': self.COLORS['negative'],
            }.get(level, '#718096')
            rows += (
                f'<tr>'
                f'<td style="padding:3px 8px;font-size:11px;font-weight:600;">{rating}</td>'
                f'<td style="padding:3px 8px;text-align:right;font-size:11px;">'
                f'{info["bps"]:.0f}bp</td>'
                f'<td style="padding:3px 8px;text-align:right;font-size:11px;">'
                f'{info["pctl"]:.0f}th</td>'
                f'<td style="padding:3px 8px;text-align:center;font-size:10px;'
                f'color:{level_color};font-weight:600;">{level}</td>'
                f'</tr>'
            )

        return (
            f'<div style="margin:20px 0;">'
            f'<div style="font-size:16px;font-weight:700;color:{self.COLORS["primary"]};'
            f'border-bottom:2px solid {self.COLORS["accent"]};padding-bottom:6px;margin-bottom:12px;">'
            f'Credit Risk Monitor</div>'
            f'<div style="text-align:center;margin:10px 0;">{chart_img}</div>'
            f'<div style="display:inline-block;padding:6px 16px;background:{zone_color};color:white;'
            f'border-radius:20px;font-size:12px;font-weight:700;margin:8px 0;">'
            f'Stress: {r["stress_score"]:.0f}/100 — {r["stress_zone"]}</div>'
            f'<table style="width:100%;border-collapse:collapse;margin:10px 0;">'
            f'<tr style="border-bottom:1px solid #e2e8f0;">'
            f'<th style="text-align:left;padding:3px 8px;font-size:10px;">Rating</th>'
            f'<th style="text-align:right;padding:3px 8px;font-size:10px;">Spread</th>'
            f'<th style="text-align:right;padding:3px 8px;font-size:10px;">Pctl</th>'
            f'<th style="text-align:center;padding:3px 8px;font-size:10px;">Level</th></tr>'
            f'{rows}</table>'
            f'<p style="font-size:11px;color:#4a4a4a;margin-top:10px;line-height:1.5;">'
            f'{r["interpretation"]}</p>'
            f'</div>'
        )

    # ── Council input (plain text) ──────────────────────────

    def get_council_input(self) -> str:
        if not self._result or 'error' in self._result:
            return "[CREDIT RISK MONITOR MODULE] Data unavailable.\n"

        r = self._result

        lines = [
            "[CREDIT RISK MONITOR MODULE — Monitor de Riesgo Crediticio (mide el estrés en los mercados de deuda corporativa a través de spreads — diferencia entre tasas corporativas y bonos del Tesoro; spreads altos = mayor percepción de riesgo)]",
            f"Score de Estrés Crediticio: {r['stress_score']:.0f}/100 ({r['stress_zone']})",
            f"Investment Grade (Grado de Inversión, empresas con rating BBB o superior): {r['ig_regime']} (total {r['ig_bps']:.0f}bps, percentil {r['ig_pctl']:.0f})",
        ]

        # IG per-rating
        ig_parts = []
        for rating in ['AAA', 'AA', 'A', 'BBB']:
            info = r.get('ig_ratings', {}).get(rating)
            if info:
                ig_parts.append(f"{rating}: {info['bps']:.0f}bps ({info['pctl']:.0f}th pctl)")
        if ig_parts:
            lines.append(f"  {' | '.join(ig_parts)}")

        lines.append(
            f"High Yield (Alto Rendimiento, empresas con rating BB o inferior — mayor riesgo): {r['hy_regime']} (total {r['hy_bps']:.0f}bps, percentil {r['hy_pctl']:.0f})"
        )

        # HY per-rating
        hy_parts = []
        for rating in ['BB', 'B', 'CCC']:
            info = r.get('hy_ratings', {}).get(rating)
            if info:
                hy_parts.append(f"{rating}: {info['bps']:.0f}bps ({info['pctl']:.0f}th pctl)")
        if hy_parts:
            lines.append(f"  {' | '.join(hy_parts)}")

        lines.append(f"Rotación de calidad (flujo entre IG y HY): {r['quality_signal']}" +
                      (f" ({r['quality_rationale']})" if r.get('quality_rationale') else ''))

        alerts = r.get('widening_alerts', [])
        lines.append(f"Alertas de ampliación de spreads: {', '.join(alerts) if alerts else 'Ninguna'}")

        # Key risk from interpretation
        interp = r.get('interpretation', '')
        if interp:
            lines.append(f"Riesgo clave: {interp.split('. ')[-1] if '. ' in interp else interp}")

        return "\n".join(lines)


if __name__ == "__main__":
    cr = CreditRiskMonitor(verbose=True)
    result = cr.run()
    print(f"\nStress Score: {result['result'].get('stress_score')}")
    print(f"Zone: {result['result'].get('stress_zone')}")
    print(f"Errors: {result['errors']}")
    print(f"\nCouncil input:\n{cr.get_council_input()}")
