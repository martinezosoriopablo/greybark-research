# -*- coding: utf-8 -*-
"""
Greybark Research - Market Temperature Module
==============================================
Composite 0-100 index measuring market "temperature" (Howard Marks style).
6 components normalized to 0-100, weighted average = Market Temperature.

Usage:
    from modules.market_temperature import MarketTemperature
    mt = MarketTemperature()
    result = mt.run()
    html = mt.get_report_section()
    text = mt.get_council_input()
"""

from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional, List, Tuple

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


class MarketTemperature(AnalyticsModuleBase):

    MODULE_NAME = "market_temperature"

    WEIGHTS = {
        'vix': 0.20,
        'credit_spread': 0.20,
        'yield_curve': 0.15,
        'pe_deviation': 0.15,
        'chile_breakeven': 0.15,
        'ipsa_momentum': 0.15,
    }

    ZONES: List[Tuple[float, float, str, str]] = [
        (0, 20, 'Panico', '#c53030'),
        (20, 40, 'Miedo', '#dd6b20'),
        (40, 60, 'Neutral', '#d69e2e'),
        (60, 80, 'Optimismo', '#276749'),
        (80, 100, 'Euforia', '#805ad5'),
    ]

    # ── Data collection ─────────────────────────────────────

    def _collect_data(self) -> Dict:
        data = {}

        # 1. VIX (yfinance fallback)
        data['vix'] = self._fetch_vix()

        # 2. Credit spreads HY-IG (FRED)
        data['credit'] = self._fetch_credit_spreads()

        # 3. Yield curve 2s10s (FRED)
        data['yield_curve'] = self._fetch_yield_curve()

        # 4. P/E S&P 500 (yfinance)
        data['pe'] = self._fetch_pe()

        # 5. Chile breakeven (ChileAnalytics)
        data['chile_be'] = self._fetch_chile_breakeven()

        # 6. IPSA momentum (yfinance)
        data['ipsa'] = self._fetch_ipsa_momentum()

        return data

    def _fetch_vix(self) -> Dict:
        """Fetch VIX 1Y history."""
        try:
            if yf is None:
                return {'error': 'yfinance not installed'}
            ticker = yf.Ticker('^VIX')
            hist = ticker.history(period='1y')
            if hist.empty:
                return {'error': 'VIX: no data'}
            closes = hist['Close'].dropna()
            return {
                'current': float(closes.iloc[-1]),
                'mean_1y': float(closes.mean()),
                'std_1y': float(closes.std()),
                'series': closes,
            }
        except Exception as e:
            self._print(f"  [ERR] VIX: {e}")
            return {'error': str(e)}

    def _fetch_credit_spreads(self) -> Dict:
        """Fetch HY and IG spreads from FRED."""
        try:
            from greybark.data_sources.fred_client import FREDClient
            fred = FREDClient()
            start = date.today() - timedelta(days=400)
            hy = fred.get_series('BAMLH0A0HYM2', start_date=start)
            ig = fred.get_series('BAMLC0A0CM', start_date=start)
            if hy is None or ig is None or hy.empty or ig.empty:
                return {'error': 'Credit spreads: no data from FRED'}
            spread = hy - ig
            spread = spread.dropna().last('365D')
            return {
                'current': float(spread.iloc[-1]),
                'mean_1y': float(spread.mean()),
                'std_1y': float(spread.std()),
                'hy_current': float(hy.iloc[-1]),
                'ig_current': float(ig.iloc[-1]),
            }
        except Exception as e:
            self._print(f"  [ERR] Credit spreads: {e}")
            return {'error': str(e)}

    def _fetch_yield_curve(self) -> Dict:
        """Fetch 2Y-10Y spread from FRED."""
        try:
            from greybark.data_sources.fred_client import FREDClient
            fred = FREDClient()
            start = date.today() - timedelta(days=400)
            dgs10 = fred.get_series('DGS10', start_date=start)
            dgs2 = fred.get_series('DGS2', start_date=start)
            if dgs10 is None or dgs2 is None or dgs10.empty or dgs2.empty:
                return {'error': 'Yield curve: no data from FRED'}
            slope = (dgs10 - dgs2).dropna()
            slope_1y = slope.last('365D')
            current_bp = float(slope.iloc[-1]) * 100  # % to bp
            return {
                'current_bp': current_bp,
                'mean_1y_bp': float(slope_1y.mean()) * 100,
                'std_1y_bp': float(slope_1y.std()) * 100,
                'dgs10': float(dgs10.iloc[-1]),
                'dgs2': float(dgs2.iloc[-1]),
            }
        except Exception as e:
            self._print(f"  [ERR] Yield curve: {e}")
            return {'error': str(e)}

    def _fetch_pe(self) -> Dict:
        """Fetch S&P 500 trailing P/E."""
        try:
            if yf is None:
                return {'error': 'yfinance not installed'}
            spy = yf.Ticker('SPY')
            info = spy.info
            pe = info.get('trailingPE') or info.get('forwardPE')
            if pe is None:
                return {'error': 'P/E: not available'}
            # Historical average P/E for S&P ~18-22 range; use 20 as 5Y proxy
            return {
                'current': float(pe),
                'hist_mean': 20.5,
                'hist_std': 3.5,
            }
        except Exception as e:
            self._print(f"  [ERR] P/E: {e}")
            return {'error': str(e)}

    def _fetch_chile_breakeven(self) -> Dict:
        """Fetch Chile 5Y breakeven inflation."""
        try:
            from greybark.analytics.chile.chile_analytics import ChileAnalytics
            ca = ChileAnalytics()
            be = ca.get_breakeven_inflation()
            be5y = be.get('breakevens', {}).get('5Y')
            if be5y is None:
                return {'error': 'Chile breakeven: no 5Y data'}
            return {
                'breakeven_5y': float(be5y),
                'target': 3.0,
            }
        except Exception as e:
            self._print(f"  [ERR] Chile breakeven: {e}")
            return {'error': str(e)}

    def _fetch_ipsa_momentum(self) -> Dict:
        """Fetch IPSA MTD return."""
        try:
            if yf is None:
                return {'error': 'yfinance not installed'}
            ipsa = yf.Ticker('^IPSA')
            hist = ipsa.history(period='1mo')
            if hist.empty or len(hist) < 2:
                return {'error': 'IPSA: insufficient data'}
            first = float(hist['Close'].iloc[0])
            last = float(hist['Close'].iloc[-1])
            mtd_pct = ((last / first) - 1) * 100
            return {
                'mtd_pct': mtd_pct,
                'last_close': last,
            }
        except Exception as e:
            self._print(f"  [ERR] IPSA: {e}")
            return {'error': str(e)}

    # ── Computation ─────────────────────────────────────────

    def _compute(self) -> Dict:
        components = {}
        valid_weights = {}

        # VIX (inverted)
        vix = self._data.get('vix', {})
        if 'error' not in vix and vix.get('current') is not None:
            norm = self._z_score_to_0_100(
                vix['current'], vix['mean_1y'], vix['std_1y'], invert=True)
            components['vix'] = {
                'raw': round(vix['current'], 1),
                'label': f"VIX: {vix['current']:.1f}",
                'normalized': round(norm, 1),
            }
            valid_weights['vix'] = self.WEIGHTS['vix']

        # Credit spread (inverted)
        credit = self._data.get('credit', {})
        if 'error' not in credit and credit.get('current') is not None:
            norm = self._z_score_to_0_100(
                credit['current'], credit['mean_1y'], credit['std_1y'], invert=True)
            components['credit_spread'] = {
                'raw': round(credit['current'], 2),
                'label': f"Spread HY-IG: {credit['current']:.2f}%",
                'normalized': round(norm, 1),
            }
            valid_weights['credit_spread'] = self.WEIGHTS['credit_spread']

        # Yield curve (linear mapping)
        yc = self._data.get('yield_curve', {})
        if 'error' not in yc and yc.get('current_bp') is not None:
            bp = yc['current_bp']
            norm = max(0, min(100, (bp + 200) / 400 * 100))
            components['yield_curve'] = {
                'raw': round(bp, 0),
                'label': f"Curva 2s10s: {bp:+.0f}bp",
                'normalized': round(norm, 1),
            }
            valid_weights['yield_curve'] = self.WEIGHTS['yield_curve']

        # P/E deviation
        pe = self._data.get('pe', {})
        if 'error' not in pe and pe.get('current') is not None:
            norm = self._z_score_to_0_100(
                pe['current'], pe['hist_mean'], pe['hist_std'], invert=False)
            components['pe_deviation'] = {
                'raw': round(pe['current'], 1),
                'label': f"P/E S&P: {pe['current']:.1f}x",
                'normalized': round(norm, 1),
            }
            valid_weights['pe_deviation'] = self.WEIGHTS['pe_deviation']

        # Chile breakeven
        cb = self._data.get('chile_be', {})
        if 'error' not in cb and cb.get('breakeven_5y') is not None:
            be = cb['breakeven_5y']
            # Map: 1% → ~20, 3% → ~50, 5% → ~80
            norm = max(0, min(100, (be / 6.0) * 100))
            components['chile_breakeven'] = {
                'raw': round(be, 2),
                'label': f"BE Chile 5Y: {be:.2f}%",
                'normalized': round(norm, 1),
            }
            valid_weights['chile_breakeven'] = self.WEIGHTS['chile_breakeven']

        # IPSA momentum
        ipsa = self._data.get('ipsa', {})
        if 'error' not in ipsa and ipsa.get('mtd_pct') is not None:
            mtd = ipsa['mtd_pct']
            norm = max(0, min(100, (mtd + 5) / 10 * 100))
            components['ipsa_momentum'] = {
                'raw': round(mtd, 2),
                'label': f"IPSA MTD: {mtd:+.2f}%",
                'normalized': round(norm, 1),
            }
            valid_weights['ipsa_momentum'] = self.WEIGHTS['ipsa_momentum']

        # Weighted composite
        if valid_weights:
            total_w = sum(valid_weights.values())
            composite = sum(
                components[k]['normalized'] * (valid_weights[k] / total_w)
                for k in valid_weights
            )
        else:
            composite = 50.0

        # Zone
        zone = 'Neutral'
        zone_color = '#d69e2e'
        for lo, hi, name, color in self.ZONES:
            if lo <= composite < hi or (hi == 100 and composite == 100):
                zone = name
                zone_color = color
                break

        # Interpretation
        n_components = len(components)
        interp = self._build_interpretation(composite, zone, components)

        return {
            'composite_score': round(composite, 1),
            'zone': zone,
            'zone_color': zone_color,
            'components': components,
            'n_components': n_components,
            'interpretation': interp,
        }

    def _build_interpretation(self, score: float, zone: str,
                              components: Dict) -> str:
        if zone == 'Panico':
            tone = "Mercado en zona de panico. Multiples indicadores senalan estres extremo."
        elif zone == 'Miedo':
            tone = "Mercado en zona de miedo. Cautela elevada entre inversores."
        elif zone == 'Neutral':
            tone = "Mercado en zona neutral. Sin senales extremas de miedo o euforia."
        elif zone == 'Optimismo':
            tone = "Mercado en zona de optimismo. Apetito por riesgo elevado."
        else:
            tone = "Mercado en zona de euforia. Extrema complacencia — atencion a reversiones."

        # Hottest / coldest component
        if components:
            hottest = max(components, key=lambda k: components[k]['normalized'])
            coldest = min(components, key=lambda k: components[k]['normalized'])
            detail = (
                f" Componente mas caliente: {components[hottest]['label']} "
                f"({components[hottest]['normalized']:.0f}/100). "
                f"Mas frio: {components[coldest]['label']} "
                f"({components[coldest]['normalized']:.0f}/100)."
            )
        else:
            detail = ""

        return f"{tone}{detail}"

    # ── Chart: semicircle gauge ─────────────────────────────

    def _generate_chart(self) -> str:
        if not HAS_MPL:
            return self._create_placeholder("Termometro de Mercado")

        score = self._result.get('composite_score', 50)
        zone = self._result.get('zone', 'Neutral')
        zone_color = self._result.get('zone_color', '#d69e2e')

        fig, ax = plt.subplots(1, 1, figsize=(5, 3.2))
        ax.set_xlim(-1.3, 1.3)
        ax.set_ylim(-0.3, 1.3)
        ax.set_aspect('equal')
        ax.axis('off')

        # Draw zone arcs
        for lo, hi, name, color in self.ZONES:
            theta1 = 180 - (hi / 100 * 180)
            theta2 = 180 - (lo / 100 * 180)
            wedge = mpatches.Wedge(
                (0, 0), 1.0, theta1, theta2,
                width=0.3, facecolor=color, edgecolor='white',
                linewidth=1.5, alpha=0.85,
            )
            ax.add_patch(wedge)
            # Zone label
            mid_angle = (theta1 + theta2) / 2
            lx = 0.62 * np.cos(np.radians(mid_angle))
            ly = 0.62 * np.sin(np.radians(mid_angle))
            ax.text(lx, ly, name, ha='center', va='center',
                    fontsize=6, color='#4a4a4a', fontweight='bold')

        # Needle
        angle = 180 - (score / 100 * 180)
        needle_r = 0.78
        nx = needle_r * np.cos(np.radians(angle))
        ny = needle_r * np.sin(np.radians(angle))
        ax.plot([0, nx], [0, ny], color=self.COLORS['primary'],
                linewidth=2.5, solid_capstyle='round')
        ax.plot(0, 0, 'o', color=self.COLORS['primary'], markersize=6)

        # Score text
        ax.text(0, -0.12, f"{score:.0f}", ha='center', va='center',
                fontsize=22, fontweight='bold', color=zone_color)
        ax.text(0, -0.25, zone.upper(), ha='center', va='center',
                fontsize=9, fontweight='bold', color=zone_color)

        fig.tight_layout()
        return self._fig_to_base64(fig)

    # ── Report section (HTML) ───────────────────────────────

    def get_report_section(self) -> str:
        if not self._result or 'error' in self._result:
            return '<div style="color:#718096;">Market Temperature: datos no disponibles</div>'

        score = self._result['composite_score']
        zone = self._result['zone']
        zone_color = self._result['zone_color']
        components = self._result.get('components', {})
        interp = self._result.get('interpretation', '')
        chart = self._chart or self._create_placeholder("Termometro de Mercado")

        # Component rows
        rows = ''
        for key, comp in components.items():
            bar_w = comp['normalized']
            rows += (
                f'<tr>'
                f'<td style="padding:4px 8px;font-size:11px;">{comp["label"]}</td>'
                f'<td style="padding:4px 8px;text-align:right;font-size:11px;font-weight:600;">'
                f'{comp["normalized"]:.0f}</td>'
                f'<td style="padding:4px 8px;width:120px;">'
                f'<div style="background:#e2e8f0;border-radius:3px;height:8px;">'
                f'<div style="background:{zone_color};width:{bar_w}%;height:8px;border-radius:3px;">'
                f'</div></div></td>'
                f'</tr>'
            )

        chart_img = f'<img src="{chart}" style="max-width:100%;"/>' if chart.startswith('data:') else chart

        return (
            f'<div style="margin:20px 0;">'
            f'<div style="font-size:16px;font-weight:700;color:{self.COLORS["primary"]};'
            f'border-bottom:2px solid {self.COLORS["accent"]};padding-bottom:6px;margin-bottom:12px;">'
            f'Termometro de Mercado</div>'
            f'<div style="text-align:center;margin:10px 0;">{chart_img}</div>'
            f'<table style="width:100%;border-collapse:collapse;margin:10px 0;">'
            f'<tr style="border-bottom:1px solid #e2e8f0;">'
            f'<th style="text-align:left;padding:4px 8px;font-size:11px;">Componente</th>'
            f'<th style="text-align:right;padding:4px 8px;font-size:11px;">Score</th>'
            f'<th style="padding:4px 8px;font-size:11px;"></th></tr>'
            f'{rows}</table>'
            f'<p style="font-size:11px;color:#4a4a4a;margin-top:10px;line-height:1.5;">{interp}</p>'
            f'</div>'
        )

    # ── Council input (plain text) ──────────────────────────

    def get_council_input(self) -> str:
        if not self._result or 'error' in self._result:
            return "[MARKET TEMPERATURE MODULE] Data unavailable.\n"

        score = self._result['composite_score']
        zone = self._result['zone']
        components = self._result.get('components', {})
        interp = self._result.get('interpretation', '')

        lines = [
            "[MARKET TEMPERATURE MODULE — Temperatura de Mercado (índice compuesto 0-100 que mide el nivel de riesgo/euforia del mercado; combina volatilidad, spreads crediticios, momentum y flujos)]",
            f"Score Compuesto: {score:.0f}/100 ({zone})",
            "Componentes:",
        ]
        for key, comp in components.items():
            lines.append(f"  {comp['label']} -> {comp['normalized']:.0f}/100")
        lines.append(f"Interpretación: {interp}")
        return "\n".join(lines)


if __name__ == "__main__":
    mt = MarketTemperature(verbose=True)
    result = mt.run()
    print(f"\nScore: {result['result'].get('composite_score')}")
    print(f"Zone: {result['result'].get('zone')}")
    print(f"Errors: {result['errors']}")
    print(f"\nCouncil input:\n{mt.get_council_input()}")
