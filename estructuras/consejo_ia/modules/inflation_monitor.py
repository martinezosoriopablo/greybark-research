# -*- coding: utf-8 -*-
"""
Greybark Research - Inflation Deep Dive Module
===============================================
Wraps InflationAnalytics to provide CPI decomposition, real rates,
breakeven analysis, wage-price spiral risk, and TIPS allocation signal.
Helps Macro + RF agents distinguish sticky services from transitory goods.

Usage:
    from modules.inflation_monitor import InflationMonitor
    im = InflationMonitor()
    result = im.run()
    html = im.get_report_section()
    text = im.get_council_input()
"""

from typing import Dict, Any, List, Tuple

from .base_module import AnalyticsModuleBase, HAS_MPL

if HAS_MPL:
    import matplotlib.pyplot as plt
    import numpy as np


class InflationMonitor(AnalyticsModuleBase):

    MODULE_NAME = "inflation_monitor"

    FED_TARGET = 2.0

    # ── Data collection ─────────────────────────────────────

    def _collect_data(self) -> Dict:
        from greybark.analytics.macro.inflation_analytics import InflationAnalytics
        ia = InflationAnalytics()

        data = {}

        # 1. CPI decomposition
        try:
            data['cpi'] = ia.get_cpi_decomposition()
        except Exception as e:
            self._print(f"  [ERR] CPI decomposition: {e}")
            data['cpi'] = {'error': str(e)}

        # 2. Real rates
        try:
            data['real_rates'] = ia.get_real_rates()
        except Exception as e:
            self._print(f"  [ERR] Real rates: {e}")
            data['real_rates'] = {'error': str(e)}

        # 3. Breakeven inflation
        try:
            data['breakevens'] = ia.get_breakeven_inflation()
        except Exception as e:
            self._print(f"  [ERR] Breakevens: {e}")
            data['breakevens'] = {'error': str(e)}

        # 4. Wage inflation analysis
        try:
            data['wages'] = ia.get_wage_inflation_analysis()
        except Exception as e:
            self._print(f"  [ERR] Wage analysis: {e}")
            data['wages'] = {'error': str(e)}

        # 5. TIPS allocation signal
        try:
            data['tips'] = ia.get_tips_allocation_signal()
        except Exception as e:
            self._print(f"  [ERR] TIPS signal: {e}")
            data['tips'] = {'error': str(e)}

        return data

    # ── Computation ─────────────────────────────────────────

    def _compute(self) -> Dict:
        cpi = self._data.get('cpi', {})
        real_rates = self._data.get('real_rates', {})
        breakevens = self._data.get('breakevens', {})
        wages = self._data.get('wages', {})
        tips = self._data.get('tips', {})

        # ── CPI components ──
        yoy = cpi.get('yoy_percent', {}) if 'error' not in cpi else {}
        prev = cpi.get('previous_month', {}) if 'error' not in cpi else {}

        cpi_all = self._safe_float(yoy.get('cpi_all'))
        cpi_core = self._safe_float(yoy.get('cpi_core'))
        cpi_services = self._safe_float(yoy.get('cpi_services'))
        cpi_goods = self._safe_float(yoy.get('cpi_goods'))
        cpi_shelter = self._safe_float(yoy.get('cpi_shelter'))

        prev_core = self._safe_float(prev.get('cpi_core'))
        services_goods_spread = self._safe_float(
            cpi.get('services_goods_spread')) if 'error' not in cpi else 0.0

        services_status = (cpi.get('analysis', {}).get('services', {}).get('status', '')
                           if 'error' not in cpi else '')
        goods_status = (cpi.get('analysis', {}).get('goods', {}).get('status', '')
                        if 'error' not in cpi else '')

        # ── Inflation regime ──
        services_sticky = cpi_services > 3.5
        core_rising = cpi_core > prev_core if prev_core else False

        if cpi_core > 3.0 and services_sticky:
            if core_rising:
                inflation_regime = 'REACCELERATING'
            else:
                inflation_regime = 'STICKY'
        elif cpi_core > 2.5:
            inflation_regime = 'ANCHORED'
        else:
            inflation_regime = 'DISINFLATION'

        # ── Real rates ──
        tips_10y = None
        real_rate_regime = 'N/A'
        rr_percentile = 0.0
        if 'error' not in real_rates:
            tips_10y = real_rates.get('current', {}).get('tips_10y')
            real_rate_regime = real_rates.get('policy_stance', 'NEUTRAL')
            rr_percentile = self._safe_float(real_rates.get('percentile_5y'))

        # ── Breakevens ──
        be_5y = None
        be_10y = None
        be_fwd = None
        be_status = 'N/A'
        if 'error' not in breakevens:
            current_be = breakevens.get('current', {})
            be_5y = current_be.get('breakeven_5y')
            be_10y = current_be.get('breakeven_10y')
            be_fwd = current_be.get('forward_5y5y')
            be_status = breakevens.get('status', 'N/A')

        # ── Wage-price spiral ──
        wage_yoy = None
        wage_cpi = None
        real_wage = None
        spiral_risk = 'N/A'
        if 'error' not in wages:
            wage_current = wages.get('current', {})
            wage_yoy = wage_current.get('wage_growth_yoy')
            wage_cpi = wage_current.get('cpi_yoy')
            real_wage = wage_current.get('real_wage_growth')
            spiral_risk = wages.get('spiral_risk', 'LOW')

        # ── TIPS signal ──
        tips_signal = 'N/A'
        tips_rationale = ''
        if 'error' not in tips:
            raw_signal = tips.get('signal', 'NEUTRAL')
            signal_map = {
                'OVERWEIGHT_TIPS': 'OW',
                'NEUTRAL_LEAN_TIPS': 'OW',
                'OVERWEIGHT_NOMINAL': 'UW',
                'NEUTRAL': 'N',
            }
            tips_signal = signal_map.get(raw_signal, 'N')
            tips_rationale = tips.get('rationale', '')

        # ── Interpretation ──
        interp = self._build_interpretation(
            inflation_regime, services_sticky, real_rate_regime,
            spiral_risk, tips_signal, be_status)

        return {
            'inflation_regime': inflation_regime,
            'cpi_all': cpi_all,
            'cpi_core': cpi_core,
            'cpi_core_prev': prev_core,
            'cpi_services': cpi_services,
            'cpi_goods': cpi_goods,
            'cpi_shelter': cpi_shelter,
            'services_goods_spread': services_goods_spread,
            'services_status': services_status,
            'goods_status': goods_status,
            'services_sticky': services_sticky,
            'real_rate_regime': real_rate_regime,
            'tips_10y': tips_10y,
            'rr_percentile': rr_percentile,
            'be_5y': be_5y,
            'be_10y': be_10y,
            'be_forward_5y5y': be_fwd,
            'be_status': be_status,
            'wage_yoy': wage_yoy,
            'wage_cpi': wage_cpi,
            'real_wage_growth': real_wage,
            'wage_spiral_risk': spiral_risk,
            'tips_signal': tips_signal,
            'tips_rationale': tips_rationale,
            'interpretation': interp,
        }

    def _build_interpretation(self, regime: str, services_sticky: bool,
                              rr_regime: str, spiral_risk: str,
                              tips_signal: str, be_status: str) -> str:
        parts = []
        regime_desc = {
            'REACCELERATING': "Inflation reaccelerating — core rising with sticky services. Fed under pressure.",
            'STICKY': "Inflation sticky — services elevated but core not rising. Slower normalization.",
            'ANCHORED': "Inflation near target — gradual normalization underway.",
            'DISINFLATION': "Disinflation trend intact — core below 2.5%, goods deflating.",
        }
        parts.append(regime_desc.get(regime, ''))

        if services_sticky:
            parts.append("Services CPI remains above 3.5% — shelter and healthcare persistent.")

        if rr_regime == 'RESTRICTIVE':
            parts.append("Real rates restrictive — tightening financial conditions.")
        elif rr_regime == 'ACCOMMODATIVE':
            parts.append("Real rates accommodative — supportive for risk assets.")

        if spiral_risk in ('HIGH', 'MODERATE'):
            parts.append(f"Wage-price spiral risk: {spiral_risk}.")

        if be_status == 'ELEVATED':
            parts.append("Market-implied inflation expectations elevated.")
        elif be_status == 'LOW':
            parts.append("Breakevens suggest market pricing disinflation.")

        return " ".join(parts)

    # ── Chart ───────────────────────────────────────────────

    def _generate_chart(self) -> str:
        if not HAS_MPL or 'error' in self._result:
            return self._create_placeholder("Inflation Monitor")

        r = self._result

        fig, axes = plt.subplots(2, 1, figsize=(8, 5.5),
                                  gridspec_kw={'height_ratios': [1.2, 1]})

        # ── Top: CPI components bar chart ──
        ax = axes[0]
        components = {
            'All Items': r.get('cpi_all', 0),
            'Core': r.get('cpi_core', 0),
            'Services': r.get('cpi_services', 0),
            'Goods': r.get('cpi_goods', 0),
            'Shelter': r.get('cpi_shelter', 0),
        }

        labels = list(components.keys())
        values = list(components.values())
        x = np.arange(len(labels))
        bar_colors = []
        for v in values:
            if v > 3.0:
                bar_colors.append(self.COLORS['negative'])
            elif v > 2.0:
                bar_colors.append(self.COLORS['accent'])
            elif v < 0:
                bar_colors.append('#2b6cb0')
            else:
                bar_colors.append(self.COLORS['positive'])

        bars = ax.bar(x, values, color=bar_colors, width=0.55, alpha=0.85)
        ax.axhline(self.FED_TARGET, color='#c53030', linewidth=1.2,
                    linestyle='--', alpha=0.7, label=f'Fed target ({self.FED_TARGET}%)')
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=8)
        ax.set_ylabel('YoY %', fontsize=8, color=self.COLORS['text_medium'])
        ax.set_title('CPI Decomposition (YoY %)', fontsize=10,
                      fontweight='bold', color=self.COLORS['primary'])
        ax.legend(fontsize=7, loc='upper right')

        for bar, val in zip(bars, values):
            if val != 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.08,
                        f'{val:.1f}%', ha='center', va='bottom', fontsize=7.5,
                        fontweight='bold')

        for spine in ['top', 'right']:
            ax.spines[spine].set_visible(False)

        # ── Bottom: Breakevens horizontal bars ──
        ax2 = axes[1]
        be_data = {}
        if r.get('be_5y') is not None:
            be_data['5Y Breakeven'] = r['be_5y']
        if r.get('be_10y') is not None:
            be_data['10Y Breakeven'] = r['be_10y']
        if r.get('be_forward_5y5y') is not None:
            be_data['5Y5Y Forward'] = r['be_forward_5y5y']
        if r.get('tips_10y') is not None:
            be_data['Real Rate (10Y TIPS)'] = r['tips_10y']

        if be_data:
            labels_be = list(be_data.keys())
            values_be = list(be_data.values())
            y_pos = np.arange(len(labels_be))

            be_colors = []
            for v in values_be:
                if v > 2.5:
                    be_colors.append(self.COLORS['accent'])
                elif v > 1.5:
                    be_colors.append(self.COLORS['positive'])
                elif v < 0:
                    be_colors.append('#2b6cb0')
                else:
                    be_colors.append(self.COLORS['text_light'])

            ax2.barh(y_pos, values_be, color=be_colors, height=0.5, alpha=0.85)
            ax2.set_yticks(y_pos)
            ax2.set_yticklabels(labels_be, fontsize=8)
            ax2.axvline(self.FED_TARGET, color='#c53030', linewidth=1.0,
                        linestyle='--', alpha=0.6)

            for i, v in enumerate(values_be):
                ax2.text(v + 0.05, i, f'{v:.2f}%', ha='left', va='center',
                         fontsize=7.5, fontweight='bold')

            ax2.set_xlabel('Rate (%)', fontsize=8, color=self.COLORS['text_medium'])
            ax2.set_title('Breakevens & Real Rates', fontsize=10,
                          fontweight='bold', color=self.COLORS['primary'])
            for spine in ['top', 'right']:
                ax2.spines[spine].set_visible(False)
        else:
            ax2.text(0.5, 0.5, 'No breakeven data', ha='center', va='center',
                     transform=ax2.transAxes, color=self.COLORS['text_light'])
            ax2.axis('off')

        fig.tight_layout()
        return self._fig_to_base64(fig)

    # ── Report section (HTML) ───────────────────────────────

    def get_report_section(self) -> str:
        if not self._result or 'error' in self._result:
            return '<div style="color:#718096;">Inflation Monitor: datos no disponibles</div>'

        r = self._result
        regime = r.get('inflation_regime', 'N/A')
        regime_colors = {
            'REACCELERATING': '#c53030', 'STICKY': '#dd6b20',
            'ANCHORED': '#276749', 'DISINFLATION': '#2b6cb0',
        }
        regime_color = regime_colors.get(regime, '#718096')

        chart = self._chart or self._create_placeholder("Inflation Monitor")
        chart_img = f'<img src="{chart}" style="max-width:100%;"/>' if chart.startswith('data:') else chart

        # CPI table
        cpi_rows = ''
        for label, key in [('All Items', 'cpi_all'), ('Core', 'cpi_core'),
                           ('Services', 'cpi_services'), ('Goods', 'cpi_goods'),
                           ('Shelter', 'cpi_shelter')]:
            val = r.get(key)
            if val is not None:
                color = self.COLORS['negative'] if val > 3.0 else self.COLORS['positive']
                cpi_rows += (
                    f'<tr><td style="padding:3px 8px;font-size:11px;">{label}</td>'
                    f'<td style="padding:3px 8px;text-align:right;font-size:11px;'
                    f'font-weight:600;color:{color};">{val:.1f}%</td></tr>'
                )

        return (
            f'<div style="margin:20px 0;">'
            f'<div style="font-size:16px;font-weight:700;color:{self.COLORS["primary"]};'
            f'border-bottom:2px solid {self.COLORS["accent"]};padding-bottom:6px;margin-bottom:12px;">'
            f'Inflation Monitor</div>'
            f'<div style="text-align:center;margin:10px 0;">{chart_img}</div>'
            f'<div style="display:inline-block;padding:6px 16px;background:{regime_color};color:white;'
            f'border-radius:20px;font-size:12px;font-weight:700;margin:8px 0;">'
            f'Regime: {regime}</div>'
            f'<table style="width:100%;border-collapse:collapse;margin:10px 0;">'
            f'<tr style="border-bottom:1px solid #e2e8f0;">'
            f'<th style="text-align:left;padding:3px 8px;font-size:10px;">CPI Component</th>'
            f'<th style="text-align:right;padding:3px 8px;font-size:10px;">YoY</th></tr>'
            f'{cpi_rows}</table>'
            f'<p style="font-size:11px;color:#4a4a4a;margin-top:10px;line-height:1.5;">'
            f'{r["interpretation"]}</p>'
            f'</div>'
        )

    # ── Council input (plain text) ──────────────────────────

    def get_council_input(self) -> str:
        if not self._result or 'error' in self._result:
            return "[INFLATION MONITOR MODULE] Data unavailable.\n"

        r = self._result

        def _fmt(v, suffix='%'):
            return f"{v:.1f}{suffix}" if v is not None else 'N/A'

        def _fmt2(v, suffix='%'):
            return f"{v:.2f}{suffix}" if v is not None else 'N/A'

        prev_str = f" (prev: {r['cpi_core_prev']:.1f}%)" if r.get('cpi_core_prev') else ''

        lines = [
            "[INFLATION MONITOR MODULE]",
            f"Inflation regime: {r['inflation_regime']}",
            "CPI decomposition:",
            f"  All items: {_fmt(r.get('cpi_all'))} YoY",
            f"  Core: {_fmt(r.get('cpi_core'))}{prev_str}",
            f"  Services: {_fmt(r.get('cpi_services'))} ({r.get('services_status', 'N/A')})",
            f"  Goods: {_fmt(r.get('cpi_goods'))} ({r.get('goods_status', 'N/A')})",
            f"  Shelter: {_fmt(r.get('cpi_shelter'))}",
            f"  Services-Goods spread: {r.get('services_goods_spread', 0):.1f}pp",
            f"Real rates: TIPS 10Y = {_fmt2(r.get('tips_10y'))} ({r['real_rate_regime']}, {r.get('rr_percentile', 0):.0f}th percentile)",
            f"Breakevens: 5Y={_fmt2(r.get('be_5y'))}, 10Y={_fmt2(r.get('be_10y'))}, 5Y5Y={_fmt2(r.get('be_forward_5y5y'))} ({r.get('be_status', 'N/A')})",
        ]

        if r.get('wage_yoy') is not None:
            lines.append(
                f"Wage-price spiral risk: {r['wage_spiral_risk']} "
                f"(wages {r['wage_yoy']:.1f}% vs CPI {r.get('wage_cpi', 0):.1f}%)"
            )

        lines.append(f"TIPS signal: {r['tips_signal']}" +
                      (f" ({r['tips_rationale']})" if r.get('tips_rationale') else ''))

        return "\n".join(lines)


if __name__ == "__main__":
    im = InflationMonitor(verbose=True)
    result = im.run()
    print(f"\nRegime: {result['result'].get('inflation_regime')}")
    print(f"Real rate regime: {result['result'].get('real_rate_regime')}")
    print(f"Errors: {result['errors']}")
    print(f"\nCouncil input:\n{im.get_council_input()}")
