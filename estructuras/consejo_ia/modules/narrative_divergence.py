# -*- coding: utf-8 -*-
"""
Greybark Research - Narrative Divergence Module
================================================
Compares AI Council narrative vs live market data to detect divergences.
5 checks: regime vs VIX, Fed vs rates, Chile OW vs IPSA, risk vs credit, conviction vs equity.

Usage:
    from modules.narrative_divergence import NarrativeDivergence
    nd = NarrativeDivergence()
    result = nd.run()
"""

from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional

from .base_module import AnalyticsModuleBase, HAS_MPL
from .narrative_parser import load_all_sessions, NarrativeDimensions

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


# Status constants
ALIGNED = 'ALIGNED'
MILD = 'MILD_DIVERGENCE'
STRONG = 'STRONG_DIVERGENCE'


class NarrativeDivergence(AnalyticsModuleBase):

    MODULE_NAME = "narrative_divergence"

    # ── Data collection ─────────────────────────────────────

    def _collect_data(self) -> Dict:
        data = {}

        # 1. Latest council session
        sessions = load_all_sessions()
        if sessions:
            data['latest_session'] = sessions[-1]
            data['session_date'] = sessions[-1].session_date
            self._print(f"  Latest session: {sessions[-1].session_date}")
        else:
            data['latest_session'] = None
            self._print("  [WARN] No council sessions found")

        # 2. Market data
        data['vix'] = self._fetch_vix()
        data['rates_10y'] = self._fetch_10y_direction()
        data['ipsa_vs_spy'] = self._fetch_ipsa_vs_spy()
        data['hy_spread'] = self._fetch_hy_spread_direction()
        data['spy_return'] = self._fetch_spy_return()

        return data

    def _fetch_vix(self) -> Dict:
        try:
            if yf is None:
                return {'error': 'yfinance not installed'}
            ticker = yf.Ticker('^VIX')
            hist = ticker.history(period='5d')
            if hist.empty:
                return {'error': 'VIX: no data'}
            current = float(hist['Close'].dropna().iloc[-1])
            return {'current': current}
        except Exception as e:
            self._print(f"  [ERR] VIX: {e}")
            return {'error': str(e)}

    def _fetch_10y_direction(self) -> Dict:
        try:
            from greybark.data_sources.fred_client import FREDClient
            fred = FREDClient()
            dgs10 = fred.get_series('DGS10', start_date=date.today() - timedelta(days=60))
            if dgs10 is None or len(dgs10.dropna()) < 22:
                return {'error': '10Y: insufficient data'}
            clean = dgs10.dropna()
            current = float(clean.iloc[-1])
            month_ago = float(clean.iloc[-22])
            change = current - month_ago
            direction = 'RISING' if change > 0.1 else ('FALLING' if change < -0.1 else 'STABLE')
            return {
                'current': current,
                'month_ago': month_ago,
                'change_bp': round(change * 100, 0),
                'direction': direction,
            }
        except Exception as e:
            self._print(f"  [ERR] 10Y: {e}")
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

            ipsa_underperforming = diff < -2
            return {
                'ipsa_ret': round(ipsa_ret, 2),
                'spy_ret': round(spy_ret, 2),
                'diff_pp': round(diff, 2),
                'ipsa_underperforming': ipsa_underperforming,
            }
        except Exception as e:
            self._print(f"  [ERR] IPSA vs SPY: {e}")
            return {'error': str(e)}

    def _fetch_hy_spread_direction(self) -> Dict:
        try:
            from greybark.data_sources.fred_client import FREDClient
            fred = FREDClient()
            hy = fred.get_series('BAMLH0A0HYM2', start_date=date.today() - timedelta(days=60))
            if hy is None or len(hy.dropna()) < 22:
                return {'error': 'HY spreads: insufficient data'}
            clean = hy.dropna()
            current = float(clean.iloc[-1])
            month_ago = float(clean.iloc[-22])
            change = current - month_ago
            direction = 'WIDENING' if change > 0.1 else ('NARROWING' if change < -0.1 else 'STABLE')
            return {
                'current': current,
                'month_ago': month_ago,
                'change': round(change, 2),
                'direction': direction,
            }
        except Exception as e:
            self._print(f"  [ERR] HY spreads: {e}")
            return {'error': str(e)}

    def _fetch_spy_return(self) -> Dict:
        try:
            if yf is None:
                return {'error': 'yfinance not installed'}
            spy = yf.Ticker('SPY')
            hist = spy.history(period='2mo')
            if hist.empty or len(hist) < 20:
                return {'error': 'SPY: insufficient data'}
            closes = hist['Close'].dropna()
            idx = max(0, len(closes) - 22)
            ret = (float(closes.iloc[-1]) / float(closes.iloc[idx]) - 1) * 100
            return {'return_1m': round(ret, 2)}
        except Exception as e:
            self._print(f"  [ERR] SPY: {e}")
            return {'error': str(e)}

    # ── Computation ─────────────────────────────────────────

    def _compute(self) -> Dict:
        session: Optional[NarrativeDimensions] = self._data.get('latest_session')
        if session is None:
            return {'error': 'No council session available'}

        checks = {}
        total_score = 0
        max_possible = 0

        # 1. Regime vs VIX
        checks['regime_vs_vix'] = self._check_regime_vs_vix(session)

        # 2. Fed stance vs rates
        checks['fed_vs_rates'] = self._check_fed_vs_rates(session)

        # 3. Chile OW vs IPSA
        checks['chile_vs_ipsa'] = self._check_chile_vs_ipsa(session)

        # 4. Risk vs credit spreads
        checks['risk_vs_credit'] = self._check_risk_vs_credit(session)

        # 5. Conviction vs equity
        checks['conviction_vs_equity'] = self._check_conviction_vs_equity(session)

        # Aggregate
        for check in checks.values():
            if check.get('score') is not None:
                total_score += check['score']
                max_possible += 2

        if max_possible > 0:
            divergence_pct = round(total_score / max_possible * 100, 1)
        else:
            divergence_pct = 0.0

        if divergence_pct < 30:
            overall = 'LOW'
        elif divergence_pct < 60:
            overall = 'MODERATE'
        else:
            overall = 'HIGH'

        # Critical divergences (score == 2)
        critical = [k for k, v in checks.items() if v.get('score', 0) == 2]

        return {
            'session_date': session.session_date,
            'checks': checks,
            'total_score': total_score,
            'max_possible': max_possible,
            'divergence_pct': divergence_pct,
            'overall': overall,
            'critical_divergences': critical,
        }

    def _check_regime_vs_vix(self, session: NarrativeDimensions) -> Dict:
        """Regime EXPANSION but VIX >25 = STRONG divergence."""
        vix = self._data.get('vix', {})
        if 'error' in vix or session.regime_call is None:
            return {'status': 'N/A', 'score': None, 'narrative': session.regime_call,
                    'market': 'VIX unavailable', 'detail': ''}

        vix_val = vix['current']
        regime = session.regime_call
        narrative_label = f"Regime: {regime}"
        market_label = f"VIX: {vix_val:.1f}"

        if regime == 'EXPANSION' and vix_val > 25:
            return {'status': STRONG, 'score': 2, 'narrative': narrative_label,
                    'market': market_label,
                    'detail': f'Council calls EXPANSION but VIX at {vix_val:.1f} signals stress.'}
        if regime == 'EXPANSION' and vix_val > 20:
            return {'status': MILD, 'score': 1, 'narrative': narrative_label,
                    'market': market_label,
                    'detail': f'Council calls EXPANSION but VIX elevated at {vix_val:.1f}.'}
        if regime in ('RECESSION', 'STAGFLATION') and vix_val < 15:
            return {'status': MILD, 'score': 1, 'narrative': narrative_label,
                    'market': market_label,
                    'detail': f'Council calls {regime} but VIX complacent at {vix_val:.1f}.'}
        return {'status': ALIGNED, 'score': 0, 'narrative': narrative_label,
                'market': market_label, 'detail': 'Regime and VIX consistent.'}

    def _check_fed_vs_rates(self, session: NarrativeDimensions) -> Dict:
        """Fed HAWKISH but 10Y FALLING = STRONG divergence."""
        rates = self._data.get('rates_10y', {})
        if 'error' in rates or session.fed_stance is None:
            return {'status': 'N/A', 'score': None, 'narrative': session.fed_stance,
                    'market': '10Y unavailable', 'detail': ''}

        direction = rates['direction']
        change_bp = rates['change_bp']
        fed = session.fed_stance
        narrative_label = f"Fed: {fed}"
        market_label = f"10Y: {direction} ({change_bp:+.0f}bp)"

        if fed == 'HAWKISH' and direction == 'FALLING':
            return {'status': STRONG, 'score': 2, 'narrative': narrative_label,
                    'market': market_label,
                    'detail': f'Council narrative is HAWKISH but 10Y yields have been FALLING.'}
        if fed == 'DOVISH' and direction == 'RISING':
            return {'status': STRONG, 'score': 2, 'narrative': narrative_label,
                    'market': market_label,
                    'detail': f'Council narrative is DOVISH but 10Y yields have been RISING.'}
        if fed == 'HAWKISH' and direction == 'STABLE':
            return {'status': MILD, 'score': 1, 'narrative': narrative_label,
                    'market': market_label,
                    'detail': 'Council narrative is HAWKISH but rates stable.'}
        return {'status': ALIGNED, 'score': 0, 'narrative': narrative_label,
                'market': market_label, 'detail': 'Fed stance and rates consistent.'}

    def _check_chile_vs_ipsa(self, session: NarrativeDimensions) -> Dict:
        """Chile OW but IPSA underperforming SPY = divergence."""
        ipsa_spy = self._data.get('ipsa_vs_spy', {})
        if 'error' in ipsa_spy or session.chile_positioning is None:
            return {'status': 'N/A', 'score': None, 'narrative': session.chile_positioning,
                    'market': 'IPSA/SPY unavailable', 'detail': ''}

        pos = session.chile_positioning
        diff = ipsa_spy['diff_pp']
        underperforming = ipsa_spy['ipsa_underperforming']
        narrative_label = f"Chile: {pos}"
        market_label = f"IPSA vs SPY: {diff:+.1f}pp"

        if pos == 'OW' and underperforming:
            severity = STRONG if diff < -5 else MILD
            score = 2 if diff < -5 else 1
            return {'status': severity, 'score': score, 'narrative': narrative_label,
                    'market': market_label,
                    'detail': f'Council overweights Chile but IPSA underperforming SPY by {abs(diff):.1f}pp.'}
        if pos == 'UW' and diff > 3:
            return {'status': MILD, 'score': 1, 'narrative': narrative_label,
                    'market': market_label,
                    'detail': f'Council underweights Chile but IPSA outperforming SPY by {diff:.1f}pp.'}
        return {'status': ALIGNED, 'score': 0, 'narrative': narrative_label,
                'market': market_label, 'detail': 'Chile positioning and performance consistent.'}

    def _check_risk_vs_credit(self, session: NarrativeDimensions) -> Dict:
        """Risk LOW/NORMAL but HY spreads WIDENING = STRONG divergence."""
        hy = self._data.get('hy_spread', {})
        if 'error' in hy or session.risk_level is None:
            return {'status': 'N/A', 'score': None, 'narrative': session.risk_level,
                    'market': 'HY spreads unavailable', 'detail': ''}

        risk = session.risk_level
        direction = hy['direction']
        change = hy['change']
        narrative_label = f"Risk: {risk}"
        market_label = f"HY spreads: {direction} ({change:+.2f})"

        if risk in ('LOW', 'NORMAL') and direction == 'WIDENING':
            return {'status': STRONG, 'score': 2, 'narrative': narrative_label,
                    'market': market_label,
                    'detail': f'Council sees {risk} risk but HY spreads are widening ({change:+.2f}).'}
        if risk in ('ELEVATED', 'HIGH') and direction == 'NARROWING':
            return {'status': MILD, 'score': 1, 'narrative': narrative_label,
                    'market': market_label,
                    'detail': f'Council sees {risk} risk but HY spreads are narrowing.'}
        return {'status': ALIGNED, 'score': 0, 'narrative': narrative_label,
                'market': market_label, 'detail': 'Risk assessment and credit spreads consistent.'}

    def _check_conviction_vs_equity(self, session: NarrativeDimensions) -> Dict:
        """Conviction ALTA but SPY declining >2% = STRONG divergence."""
        spy = self._data.get('spy_return', {})
        if 'error' in spy or session.equity_conviction is None:
            return {'status': 'N/A', 'score': None, 'narrative': session.equity_conviction,
                    'market': 'SPY unavailable', 'detail': ''}

        conviction = session.equity_conviction
        ret = spy['return_1m']
        narrative_label = f"Conviction: {conviction}"
        market_label = f"SPY 1M: {ret:+.1f}%"

        if conviction == 'ALTA' and ret < -2:
            severity = STRONG if ret < -5 else MILD
            score = 2 if ret < -5 else 1
            return {'status': severity, 'score': score, 'narrative': narrative_label,
                    'market': market_label,
                    'detail': f'Council has ALTA conviction but SPY declined {ret:.1f}% last month.'}
        if conviction == 'BAJA' and ret > 3:
            return {'status': MILD, 'score': 1, 'narrative': narrative_label,
                    'market': market_label,
                    'detail': f'Council has BAJA conviction but SPY rallied {ret:.1f}%.'}
        return {'status': ALIGNED, 'score': 0, 'narrative': narrative_label,
                'market': market_label, 'detail': 'Conviction and equity performance consistent.'}

    # ── Chart: Visual divergence table ──────────────────────

    def _generate_chart(self) -> str:
        if not HAS_MPL or 'error' in self._result:
            return self._create_placeholder("Narrative Divergence")

        checks = self._result.get('checks', {})
        divergence_pct = self._result.get('divergence_pct', 0)
        overall = self._result.get('overall', 'LOW')

        if not checks:
            return self._create_placeholder("Narrative Divergence (sin datos)")

        status_colors = {
            ALIGNED: '#276749',
            MILD: '#dd6b20',
            STRONG: '#c53030',
            'N/A': '#718096',
        }

        labels = {
            'regime_vs_vix': 'Regime vs VIX',
            'fed_vs_rates': 'Fed vs Rates',
            'chile_vs_ipsa': 'Chile vs IPSA',
            'risk_vs_credit': 'Risk vs Credit',
            'conviction_vs_equity': 'Conviction vs Equity',
        }

        n_checks = len(checks)
        fig, ax = plt.subplots(figsize=(8, 0.6 * n_checks + 1.5))
        ax.axis('off')

        # Table header
        col_x = [0.0, 0.22, 0.45, 0.72, 0.92]
        headers = ['Check', 'Narrativa', 'Mercado', 'Status', '']
        for x, h in zip(col_x, headers):
            ax.text(x, 1.0, h, transform=ax.transAxes, fontsize=9,
                    fontweight='bold', color=self.COLORS['primary'], va='top')

        # Rows
        sorted_checks = list(checks.items())
        for i, (key, check) in enumerate(sorted_checks):
            y = 0.85 - i * (0.7 / max(n_checks, 1))
            status = check.get('status', 'N/A')
            color = status_colors.get(status, '#718096')

            ax.text(col_x[0], y, labels.get(key, key), transform=ax.transAxes,
                    fontsize=8, color=self.COLORS['text_dark'], va='top')
            ax.text(col_x[1], y, str(check.get('narrative', 'N/A')), transform=ax.transAxes,
                    fontsize=8, color=self.COLORS['text_medium'], va='top')
            ax.text(col_x[2], y, str(check.get('market', 'N/A')), transform=ax.transAxes,
                    fontsize=8, color=self.COLORS['text_medium'], va='top')

            # Status dot + label
            ax.plot(col_x[3] + 0.01, y - 0.01, 'o', color=color, markersize=8,
                    transform=ax.transAxes, clip_on=False)
            status_short = {ALIGNED: 'OK', MILD: 'MILD', STRONG: 'STRONG', 'N/A': 'N/A'}
            ax.text(col_x[3] + 0.04, y, status_short.get(status, status),
                    transform=ax.transAxes, fontsize=8, fontweight='bold',
                    color=color, va='top')

        # Summary bar at bottom
        overall_color = {'LOW': '#276749', 'MODERATE': '#dd6b20', 'HIGH': '#c53030'}
        oc = overall_color.get(overall, '#718096')
        ax.text(0.5, 0.02, f"Divergencia Total: {divergence_pct:.0f}% ({overall})",
                transform=ax.transAxes, fontsize=11, fontweight='bold',
                color=oc, ha='center', va='bottom',
                bbox=dict(boxstyle='round,pad=0.4', facecolor=oc, alpha=0.1, edgecolor=oc))

        ax.set_title('Narrative Divergence — Council vs Mercado', fontsize=11,
                      fontweight='bold', color=self.COLORS['primary'], pad=10)

        fig.tight_layout()
        return self._fig_to_base64(fig)

    # ── Report section (HTML) ───────────────────────────────

    def get_report_section(self) -> str:
        if not self._result or 'error' in self._result:
            return '<div style="color:#718096;">Narrative Divergence: datos no disponibles</div>'

        r = self._result
        chart = self._chart or self._create_placeholder("Narrative Divergence")
        chart_img = f'<img src="{chart}" style="max-width:100%;"/>' if chart.startswith('data:') else chart

        overall_color = {'LOW': '#276749', 'MODERATE': '#dd6b20', 'HIGH': '#c53030'}
        oc = overall_color.get(r['overall'], '#718096')

        # Check rows
        status_icons = {ALIGNED: '&#9679;', MILD: '&#9679;', STRONG: '&#9679;', 'N/A': '&#9675;'}
        status_colors = {ALIGNED: '#276749', MILD: '#dd6b20', STRONG: '#c53030', 'N/A': '#718096'}
        labels = {
            'regime_vs_vix': 'Regime vs VIX',
            'fed_vs_rates': 'Fed vs Rates',
            'chile_vs_ipsa': 'Chile vs IPSA',
            'risk_vs_credit': 'Risk vs Credit',
            'conviction_vs_equity': 'Conviction vs Equity',
        }

        rows = ''
        for key, check in r.get('checks', {}).items():
            status = check.get('status', 'N/A')
            sc = status_colors.get(status, '#718096')
            icon = status_icons.get(status, '&#9675;')
            rows += (
                f'<tr>'
                f'<td style="padding:4px 8px;font-size:11px;">{labels.get(key, key)}</td>'
                f'<td style="padding:4px 8px;font-size:11px;">{check.get("narrative", "N/A")}</td>'
                f'<td style="padding:4px 8px;font-size:11px;">{check.get("market", "N/A")}</td>'
                f'<td style="padding:4px 8px;font-size:12px;color:{sc};font-weight:700;text-align:center;">'
                f'{icon} {status.replace("_", " ")}</td>'
                f'</tr>'
            )

        return (
            f'<div style="margin:20px 0;">'
            f'<div style="font-size:16px;font-weight:700;color:{self.COLORS["primary"]};'
            f'border-bottom:2px solid {self.COLORS["accent"]};padding-bottom:6px;margin-bottom:12px;">'
            f'Narrative Divergence</div>'
            f'<div style="font-size:11px;color:{self.COLORS["text_light"]};margin-bottom:8px;">'
            f'Sesion analizada: {r["session_date"]}</div>'
            f'<div style="text-align:center;margin:10px 0;">{chart_img}</div>'
            f'<table style="width:100%;border-collapse:collapse;margin:10px 0;">'
            f'<tr style="border-bottom:1px solid #e2e8f0;">'
            f'<th style="text-align:left;padding:4px 8px;font-size:10px;">Check</th>'
            f'<th style="text-align:left;padding:4px 8px;font-size:10px;">Narrativa</th>'
            f'<th style="text-align:left;padding:4px 8px;font-size:10px;">Mercado</th>'
            f'<th style="text-align:center;padding:4px 8px;font-size:10px;">Status</th></tr>'
            f'{rows}</table>'
            f'<div style="text-align:center;margin:12px 0;padding:8px;background:{oc}10;'
            f'border:1px solid {oc};border-radius:8px;">'
            f'<span style="font-size:13px;font-weight:700;color:{oc};">'
            f'Divergencia Total: {r["divergence_pct"]:.0f}% ({r["overall"]})</span></div>'
            f'</div>'
        )

    # ── Council input (plain text) — THE MOST CRITICAL ──────

    def get_council_input(self) -> str:
        if not self._result or 'error' in self._result:
            return "[NARRATIVE DIVERGENCE MODULE] Data unavailable.\n"

        r = self._result
        lines = [
            "[NARRATIVE DIVERGENCE MODULE]",
            f"Latest council session: {r['session_date']}",
            f"Divergence score: {r['divergence_pct']:.0f}% ({r['overall']})",
        ]

        critical = r.get('critical_divergences', [])
        if critical:
            lines.append("CRITICAL DIVERGENCES:")
            for key in critical:
                check = r['checks'].get(key, {})
                detail = check.get('detail', '')
                label_map = {
                    'regime_vs_vix': 'Regime vs VIX',
                    'fed_vs_rates': 'Fed stance vs rates',
                    'chile_vs_ipsa': 'Chile positioning vs IPSA',
                    'risk_vs_credit': 'Risk vs credit spreads',
                    'conviction_vs_equity': 'Conviction vs equity',
                }
                lines.append(f"  {label_map.get(key, key)}: {detail}")
        else:
            lines.append("No critical divergences detected.")

        # Also list mild divergences
        mild = [k for k, v in r['checks'].items() if v.get('score') == 1]
        if mild:
            lines.append("Mild divergences:")
            for key in mild:
                check = r['checks'].get(key, {})
                detail = check.get('detail', '')
                lines.append(f"  {key}: {detail}")

        # Aligned checks
        aligned = [k for k, v in r['checks'].items() if v.get('score') == 0]
        if aligned:
            lines.append(f"Aligned: {', '.join(aligned)}")

        return "\n".join(lines)


if __name__ == "__main__":
    nd = NarrativeDivergence(verbose=True)
    result = nd.run()
    print(f"\nDivergence: {result['result'].get('divergence_pct')}%")
    print(f"Overall: {result['result'].get('overall')}")
    print(f"Errors: {result['errors']}")
    print(f"\nCouncil input:\n{nd.get_council_input()}")
