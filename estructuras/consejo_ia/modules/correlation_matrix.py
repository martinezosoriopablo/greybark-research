# -*- coding: utf-8 -*-
"""
Greybark Research - Correlation Matrix Module
==============================================
Dynamic rolling 60-day correlation between 7 asset classes.
Detects correlation breaks and stress signals (Swensen/Yale style).

Usage:
    from modules.correlation_matrix import CorrelationMatrix
    cm = CorrelationMatrix()
    result = cm.run()
"""

from datetime import datetime
from typing import Dict, Any, List

from .base_module import AnalyticsModuleBase, HAS_MPL

if HAS_MPL:
    import matplotlib.pyplot as plt
    import numpy as np

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import yfinance as yf
except ImportError:
    yf = None


class CorrelationMatrix(AnalyticsModuleBase):

    MODULE_NAME = "correlation_matrix"

    ASSETS = {
        'SPY': 'S&P 500',
        '^IPSA': 'IPSA',
        '^TNX': 'UST 10Y',
        'GC=F': 'Oro',
        'HG=F': 'Cobre',
        'DX-Y.NYB': 'DXY',
        'CLPUSD=X': 'CLP/USD',
    }

    ROLLING_WINDOW = 60
    BREAK_THRESHOLD = 0.30
    STRESS_CORR_THRESHOLD = 0.60
    LOOKBACK_CHANGE = 20

    # ── Data collection ─────────────────────────────────────

    def _collect_data(self) -> Dict:
        if yf is None or pd is None:
            return {'error': 'yfinance or pandas not installed'}

        tickers = list(self.ASSETS.keys())
        self._print(f"  Downloading {len(tickers)} tickers (6mo)...")

        try:
            raw = yf.download(
                tickers, period='6mo', interval='1d',
                auto_adjust=True, progress=False, threads=True,
            )
        except Exception as e:
            return {'error': f'yfinance download: {e}'}

        # Extract Close prices
        if isinstance(raw.columns, pd.MultiIndex):
            prices = raw['Close'] if 'Close' in raw.columns.get_level_values(0) else raw
        else:
            prices = raw

        # Rename to friendly labels
        rename = {}
        for ticker, label in self.ASSETS.items():
            if ticker in prices.columns:
                rename[ticker] = label
        prices = prices.rename(columns=rename)

        # Drop columns with >30% NaN
        threshold = len(prices) * 0.3
        prices = prices.dropna(axis=1, thresh=int(len(prices) - threshold))
        prices = prices.ffill().dropna()

        if prices.shape[1] < 3:
            return {'error': f'Only {prices.shape[1]} assets with data'}

        self._print(f"  Got {prices.shape[1]} assets, {prices.shape[0]} days")
        return {'prices': prices, 'asset_labels': list(prices.columns)}

    # ── Computation ─────────────────────────────────────────

    def _compute(self) -> Dict:
        if 'error' in self._data:
            return {'error': self._data['error']}

        prices = self._data['prices']
        labels = self._data['asset_labels']
        returns = prices.pct_change().dropna()

        if len(returns) < self.ROLLING_WINDOW + self.LOOKBACK_CHANGE:
            return {'error': f'Insufficient data: {len(returns)} days'}

        # Current 60D correlation
        current_corr = returns.iloc[-self.ROLLING_WINDOW:].corr()

        # 20 days ago 60D correlation
        end_prev = -self.LOOKBACK_CHANGE
        start_prev = end_prev - self.ROLLING_WINDOW
        prev_corr = returns.iloc[start_prev:end_prev].corr()

        # Full history average
        full_corr = returns.corr()

        # Change matrix
        change_matrix = current_corr - prev_corr

        # Detect breaks
        breaks = self._detect_breaks(current_corr, prev_corr, change_matrix, labels)

        # Detect stress signals
        stress = self._detect_stress(current_corr, full_corr, labels)

        # Average cross-asset correlation (exclude diagonal)
        n = len(labels)
        if n > 1:
            mask = ~pd.np.eye(n, dtype=bool) if hasattr(pd, 'np') else ~np.eye(n, dtype=bool)
            avg_corr = float(current_corr.values[mask].mean())
        else:
            avg_corr = 0.0

        interp = self._build_interpretation(avg_corr, breaks, stress)

        return {
            'current_matrix': current_corr.round(2).to_dict(),
            'change_matrix': change_matrix.round(2).to_dict(),
            'labels': labels,
            'breaks': breaks,
            'stress_signals': stress,
            'avg_correlation': round(avg_corr, 3),
            'n_assets': n,
            'interpretation': interp,
        }

    def _detect_breaks(self, current: 'pd.DataFrame', prev: 'pd.DataFrame',
                       change: 'pd.DataFrame', labels: list) -> List[Dict]:
        breaks = []
        n = len(labels)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = labels[i], labels[j]
                ch = float(change.iloc[i, j])
                if abs(ch) >= self.BREAK_THRESHOLD:
                    breaks.append({
                        'asset_1': a,
                        'asset_2': b,
                        'corr_now': round(float(current.iloc[i, j]), 2),
                        'corr_before': round(float(prev.iloc[i, j]), 2),
                        'change': round(ch, 2),
                    })
        breaks.sort(key=lambda x: abs(x['change']), reverse=True)
        return breaks

    def _detect_stress(self, current: 'pd.DataFrame', historical: 'pd.DataFrame',
                       labels: list) -> List[Dict]:
        stress = []
        n = len(labels)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = labels[i], labels[j]
                hist_c = abs(float(historical.iloc[i, j]))
                curr_c = abs(float(current.iloc[i, j]))
                if hist_c < 0.20 and curr_c > self.STRESS_CORR_THRESHOLD:
                    stress.append({
                        'asset_1': a,
                        'asset_2': b,
                        'corr_now': round(float(current.iloc[i, j]), 2),
                        'avg_corr': round(float(historical.iloc[i, j]), 2),
                        'signal': 'STRESS',
                    })
        return stress

    def _build_interpretation(self, avg: float, breaks: list, stress: list) -> str:
        if avg > 0.6:
            tone = "Correlaciones elevadas — diversificacion limitada, posible entorno de estres."
        elif avg > 0.3:
            tone = "Correlaciones moderadas — diversificacion funcionando parcialmente."
        else:
            tone = "Correlaciones bajas — diversificacion efectiva entre asset classes."

        parts = [tone]
        if breaks:
            parts.append(f"{len(breaks)} quiebre(s) de correlacion detectado(s) en los ultimos 20 dias.")
        if stress:
            parts.append(f"ALERTA: {len(stress)} senal(es) de estres — activos historicamente no correlacionados moviéndose juntos.")
        return " ".join(parts)

    # ── Chart: heatmap triangular ───────────────────────────

    def _generate_chart(self) -> str:
        if not HAS_MPL or 'error' in self._result:
            return self._create_placeholder("Matriz de Correlacion")

        labels = self._result['labels']
        n = len(labels)
        corr_dict = self._result['current_matrix']
        breaks = self._result.get('breaks', [])

        # Rebuild matrix as numpy array
        corr = np.zeros((n, n))
        for i, a in enumerate(labels):
            for j, b in enumerate(labels):
                corr[i, j] = corr_dict.get(a, {}).get(b, 0)

        # Mask upper triangle
        mask = np.triu(np.ones_like(corr, dtype=bool), k=0)

        fig, ax = plt.subplots(figsize=(6, 5))

        # Plot with mask
        masked_corr = np.ma.masked_where(mask, corr)
        cmap = plt.cm.RdYlGn
        im = ax.imshow(masked_corr, cmap=cmap, vmin=-1, vmax=1, aspect='auto')

        # Annotations and break borders
        break_pairs = {(b['asset_1'], b['asset_2']) for b in breaks}
        for i in range(n):
            for j in range(n):
                if j < i:  # lower triangle only
                    val = corr[i, j]
                    color = 'white' if abs(val) > 0.6 else 'black'
                    ax.text(j, i, f"{val:.2f}", ha='center', va='center',
                            fontsize=8, color=color, fontweight='bold')
                    # Red border for breaks
                    a1, a2 = labels[i], labels[j]
                    if (a1, a2) in break_pairs or (a2, a1) in break_pairs:
                        rect = plt.Rectangle((j - 0.5, i - 0.5), 1, 1,
                                             fill=False, edgecolor='red',
                                             linewidth=2.5)
                        ax.add_patch(rect)

        # Upper triangle white
        for i in range(n):
            for j in range(i, n):
                rect = plt.Rectangle((j - 0.5, i - 0.5), 1, 1,
                                     fill=True, facecolor='white', edgecolor='white')
                ax.add_patch(rect)

        ax.set_xticks(range(n))
        ax.set_yticks(range(n))
        ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
        ax.set_yticklabels(labels, fontsize=8)

        cbar = fig.colorbar(im, ax=ax, shrink=0.7, pad=0.02)
        cbar.ax.tick_params(labelsize=7)

        ax.set_title("Correlaciones Rolling 60D", fontsize=11, fontweight='bold',
                      color=self.COLORS['primary'], pad=10)

        fig.tight_layout()
        return self._fig_to_base64(fig)

    # ── Report section (HTML) ───────────────────────────────

    def get_report_section(self) -> str:
        if not self._result or 'error' in self._result:
            return '<div style="color:#718096;">Correlation Matrix: datos no disponibles</div>'

        avg = self._result['avg_correlation']
        breaks = self._result.get('breaks', [])
        stress = self._result.get('stress_signals', [])
        interp = self._result.get('interpretation', '')
        chart = self._chart or self._create_placeholder("Matriz de Correlacion")
        chart_img = f'<img src="{chart}" style="max-width:100%;"/>' if chart.startswith('data:') else chart

        # Breaks table
        breaks_html = ''
        if breaks:
            rows = ''
            for b in breaks[:5]:
                direction = '+' if b['change'] > 0 else ''
                rows += (
                    f'<tr>'
                    f'<td style="padding:3px 6px;font-size:11px;">{b["asset_1"]} / {b["asset_2"]}</td>'
                    f'<td style="padding:3px 6px;font-size:11px;text-align:center;">{b["corr_before"]}</td>'
                    f'<td style="padding:3px 6px;font-size:11px;text-align:center;">{b["corr_now"]}</td>'
                    f'<td style="padding:3px 6px;font-size:11px;text-align:center;'
                    f'color:{self.COLORS["negative"]};">{direction}{b["change"]}</td>'
                    f'</tr>'
                )
            breaks_html = (
                f'<div style="margin:10px 0;padding:8px;background:#fff5f5;border-left:3px solid {self.COLORS["negative"]};border-radius:4px;">'
                f'<div style="font-size:11px;font-weight:700;margin-bottom:6px;">Quiebres de Correlacion (20D)</div>'
                f'<table style="width:100%;border-collapse:collapse;">'
                f'<tr><th style="text-align:left;font-size:10px;padding:2px 6px;">Par</th>'
                f'<th style="font-size:10px;padding:2px 6px;">Antes</th>'
                f'<th style="font-size:10px;padding:2px 6px;">Ahora</th>'
                f'<th style="font-size:10px;padding:2px 6px;">Cambio</th></tr>'
                f'{rows}</table></div>'
            )

        # Stress alert
        stress_html = ''
        if stress:
            items = ''.join(
                f'<div style="font-size:11px;">⚠ {s["asset_1"]} / {s["asset_2"]}: '
                f'historico {s["avg_corr"]:.2f} → actual {s["corr_now"]:.2f}</div>'
                for s in stress
            )
            stress_html = (
                f'<div style="margin:10px 0;padding:8px;background:#fffff0;border-left:3px solid #d69e2e;border-radius:4px;">'
                f'<div style="font-size:11px;font-weight:700;margin-bottom:4px;">Señales de Estres</div>'
                f'{items}</div>'
            )

        return (
            f'<div style="margin:20px 0;">'
            f'<div style="font-size:16px;font-weight:700;color:{self.COLORS["primary"]};'
            f'border-bottom:2px solid {self.COLORS["accent"]};padding-bottom:6px;margin-bottom:12px;">'
            f'Matriz de Correlacion — Rolling 60D</div>'
            f'<div style="text-align:center;margin:10px 0;">{chart_img}</div>'
            f'<div style="font-size:11px;color:#4a4a4a;margin:6px 0;">Correlacion promedio cross-asset: <b>{avg:.2f}</b></div>'
            f'{breaks_html}{stress_html}'
            f'<p style="font-size:11px;color:#4a4a4a;margin-top:8px;line-height:1.5;">{interp}</p>'
            f'</div>'
        )

    # ── Council input (plain text) ──────────────────────────

    def get_council_input(self) -> str:
        if not self._result or 'error' in self._result:
            return "[CORRELATION MATRIX MODULE] Data unavailable.\n"

        avg = self._result['avg_correlation']
        breaks = self._result.get('breaks', [])
        stress = self._result.get('stress_signals', [])
        interp = self._result.get('interpretation', '')

        lines = [
            "[CORRELATION MATRIX MODULE]",
            f"Rolling 60-day cross-asset correlation (avg: {avg:.2f})",
            f"Assets: {', '.join(self._result['labels'])}",
        ]

        if breaks:
            lines.append(f"\nCorrelation breaks (last {self.LOOKBACK_CHANGE} days):")
            for b in breaks:
                lines.append(
                    f"  {b['asset_1']} / {b['asset_2']}: "
                    f"{b['corr_before']} -> {b['corr_now']} (change: {b['change']:+.2f}) *** BREAK ***"
                )
        else:
            lines.append("\nNo significant correlation breaks detected.")

        if stress:
            lines.append("\nStress signals (historically uncorrelated pairs now aligned):")
            for s in stress:
                lines.append(
                    f"  {s['asset_1']} / {s['asset_2']}: "
                    f"historical avg {s['avg_corr']:.2f}, now {s['corr_now']:.2f}"
                )

        lines.append(f"\nInterpretation: {interp}")
        return "\n".join(lines)


if __name__ == "__main__":
    cm = CorrelationMatrix(verbose=True)
    result = cm.run()
    print(f"\nAvg correlation: {result['result'].get('avg_correlation')}")
    print(f"Breaks: {len(result['result'].get('breaks', []))}")
    print(f"Stress: {len(result['result'].get('stress_signals', []))}")
    print(f"Errors: {result['errors']}")
    print(f"\nCouncil input:\n{cm.get_council_input()}")
