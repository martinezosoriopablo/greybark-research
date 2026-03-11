# -*- coding: utf-8 -*-
"""
Greybark Research - RV Chart Generator
========================================

Genera charts profesionales para el reporte de Renta Variable.
Usa datos reales del EquityDataCollector (market_data dict).

Dependencias:
- matplotlib
- numpy
"""

import base64
import io
import logging
from typing import Dict, Any, List, Optional
import warnings

warnings.filterwarnings('ignore')

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

from chart_config import get_chart_colors, get_failure_tracker

logger = logging.getLogger(__name__)


class RVChartsGenerator:
    """Generador de charts para el reporte de Renta Variable."""

    # Regiones para charts regionales (orden display)
    REGIONS = ['us', 'europe', 'em', 'japan', 'latam', 'chile']
    REGION_LABELS = {
        'us': 'EE.UU.', 'europe': 'Europa', 'em': 'Emergentes',
        'japan': 'Japón', 'latam': 'LatAm', 'chile': 'Chile',
        'china': 'China', 'brazil': 'Brasil'
    }

    # Sectores
    SECTOR_LABELS = {
        'technology': 'Tecnología', 'healthcare': 'Salud',
        'financials': 'Financiero', 'consumer_disc': 'Cons. Disc.',
        'industrials': 'Industriales', 'energy': 'Energía',
        'materials': 'Materiales', 'utilities': 'Utilities',
        'real_estate': 'Real Estate', 'comm_services': 'Comunicaciones',
        'consumer_staples': 'Cons. Básico'
    }

    def __init__(self, market_data: Dict = None, branding: Dict = None):
        self.data = market_data or {}
        # Derive colors from branding (or use Greybark defaults)
        scheme = get_chart_colors(branding)
        self.COLORS = {
            'primary': scheme.primary, 'accent': scheme.accent,
            'positive': scheme.positive, 'negative': scheme.negative,
            'neutral': scheme.neutral, 'bg_light': scheme.bg_light,
            'text_dark': scheme.text_dark, 'text_medium': scheme.text_medium,
            'text_light': scheme.text_light,
        }
        self.SERIES_COLORS = scheme.series
        self._failure_tracker = get_failure_tracker()
        self._setup_style()

    def _setup_style(self):
        if not MATPLOTLIB_AVAILABLE:
            return
        plt.rcParams.update({
            'font.family': 'sans-serif',
            'font.sans-serif': ['Segoe UI', 'Arial', 'Helvetica'],
            'font.size': 9,
            'axes.titlesize': 11,
            'axes.labelsize': 9,
            'axes.titleweight': 'bold',
            'axes.spines.top': False,
            'axes.spines.right': False,
            'figure.facecolor': 'white',
            'axes.facecolor': 'white',
            'axes.grid': True,
            'grid.alpha': 0.3,
            'grid.linestyle': '--',
        })

    def _fig_to_base64(self, fig) -> str:
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=110, bbox_inches='tight',
                    facecolor='white', edgecolor='none')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        return f"data:image/png;base64,{img_base64}"

    def _create_placeholder(self, title: str) -> str:
        return f'''
        <div style="background: #f7fafc; border: 2px dashed #e2e8f0;
                    border-radius: 8px; padding: 40px; text-align: center;
                    color: #718096; margin: 15px 0;">
            <div style="font-size: 14pt; margin-bottom: 10px;">{title}</div>
            <div style="font-size: 10pt;">Chart no disponible</div>
        </div>
        '''

    def _safe_val(self, d: Any, *keys, default=None):
        """Navega dict anidado de forma segura."""
        current = d
        for key in keys:
            if not isinstance(current, dict):
                return default
            current = current.get(key)
            if current is None:
                return default
        return current

    def generate_all_charts(self) -> Dict[str, str]:
        """Genera los 12 charts del reporte RV."""
        charts = {}
        chart_methods = {
            'rv_regional_performance': self._generate_regional_performance,
            'rv_pe_valuations': self._generate_pe_valuations,
            'rv_sector_heatmap': self._generate_sector_heatmap,
            'rv_earnings_beat': self._generate_earnings_beat,
            'rv_style_box': self._generate_style_box,
            'rv_correlation': self._generate_correlation_matrix,
            'rv_vix_range': self._generate_vix_range,
            'rv_chile_ipsa_copper': self._generate_chile_ipsa_copper,
            'rv_credit_risk': self._generate_credit_risk,
            'rv_drawdown': self._generate_drawdown,
            'rv_factor_radar': self._generate_factor_radar,
            'rv_earnings_revisions': self._generate_earnings_revisions,
        }
        for chart_id, method in chart_methods.items():
            try:
                charts[chart_id] = method()
            except Exception as e:
                self._failure_tracker.record(chart_id, str(e), fallback_used=True)
                logger.warning("Chart '%s' failed: %s", chart_id, e)
                charts[chart_id] = self._create_placeholder(chart_id)
        return charts

    # =========================================================================
    # 1. REGIONAL PERFORMANCE — Horizontal grouped bar
    # =========================================================================

    def _generate_regional_performance(self) -> str:
        """Retornos regionales: 1M, 3M, YTD por region."""
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder('Performance Regional')

        valuations = self.data.get('valuations', {})
        if not valuations:
            return self._create_placeholder('Performance Regional — sin datos')

        regions = []
        ret_1m, ret_3m, ret_ytd = [], [], []

        for key in self.REGIONS:
            v = valuations.get(key, {})
            returns = v.get('returns', {})
            if not returns:
                continue
            regions.append(self.REGION_LABELS.get(key, key))
            ret_1m.append(returns.get('1m', 0) or 0)
            ret_3m.append(returns.get('3m', 0) or 0)
            ret_ytd.append(returns.get('ytd', 0) or 0)

        if not regions:
            return self._create_placeholder('Performance Regional — sin datos')

        n = len(regions)
        fig, ax = plt.subplots(figsize=(8, max(3.5, 0.5 * n + 1)))

        y = np.arange(n)
        bar_h = 0.25

        bars_ytd = ax.barh(y - bar_h, ret_ytd, bar_h, label='YTD',
                           color=self.SERIES_COLORS[0], alpha=0.85)
        bars_3m = ax.barh(y, ret_3m, bar_h, label='3M',
                          color=self.SERIES_COLORS[1], alpha=0.85)
        bars_1m = ax.barh(y + bar_h, ret_1m, bar_h, label='1M',
                          color=self.SERIES_COLORS[2], alpha=0.85)

        # Anotaciones
        for bars in [bars_ytd, bars_3m, bars_1m]:
            for bar in bars:
                w = bar.get_width()
                if abs(w) > 0.3:
                    ax.text(w + (0.3 if w >= 0 else -0.3),
                            bar.get_y() + bar.get_height() / 2,
                            f'{w:.1f}%', va='center',
                            ha='left' if w >= 0 else 'right',
                            fontsize=7, color=self.COLORS['text_medium'])

        ax.set_yticks(y)
        ax.set_yticklabels(regions, fontsize=9)
        ax.set_xlabel('Retorno (%)', fontsize=9)
        ax.set_title('Performance Regional', fontsize=12, fontweight='bold',
                      color=self.COLORS['primary'], pad=10)
        ax.axvline(x=0, color=self.COLORS['primary'], linewidth=0.5)
        ax.legend(loc='lower right', fontsize=8)
        plt.tight_layout()
        return self._fig_to_base64(fig)

    # =========================================================================
    # 2. P/E VALUATIONS — Grouped vertical bar
    # =========================================================================

    def _generate_pe_valuations(self) -> str:
        """P/E Trailing por region con barra de comparacion."""
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder('Valorizaciones P/E')

        valuations = self.data.get('valuations', {})
        if not valuations:
            return self._create_placeholder('Valorizaciones P/E — sin datos')

        regions = []
        pe_trailing = []

        for key in self.REGIONS:
            v = valuations.get(key, {})
            pe_t = v.get('pe_trailing')
            if pe_t is None:
                continue
            regions.append(self.REGION_LABELS.get(key, key))
            pe_trailing.append(pe_t)

        if not regions:
            return self._create_placeholder('Valorizaciones P/E — sin datos')

        n = len(regions)
        fig, ax = plt.subplots(figsize=(8, 4))

        x = np.arange(n)
        bar_w = 0.5

        bars = ax.bar(x, pe_trailing, bar_w, label='P/E Trailing',
                      color=self.SERIES_COLORS[0], alpha=0.85)

        # Anotaciones
        for bar, val in zip(bars, pe_trailing):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                    f'{val:.1f}x', ha='center', va='bottom',
                    fontsize=8, fontweight='bold', color=self.COLORS['text_dark'])

        # Linea promedio
        avg_pe = np.mean(pe_trailing)
        ax.axhline(y=avg_pe, color=self.COLORS['accent'], linewidth=1.5,
                   linestyle='--', alpha=0.7, label=f'Promedio: {avg_pe:.1f}x')

        ax.set_xticks(x)
        ax.set_xticklabels(regions, fontsize=9)
        ax.set_ylabel('P/E Ratio', fontsize=9)
        ax.set_title('Valorizaciones P/E por Región', fontsize=12,
                      fontweight='bold', color=self.COLORS['primary'], pad=10)
        ax.legend(loc='upper right', fontsize=8)
        ax.set_ylim(0, max(pe_trailing) * 1.2)
        plt.tight_layout()
        return self._fig_to_base64(fig)

    # =========================================================================
    # 3. SECTOR HEATMAP — Heatmap de retornos sectoriales
    # =========================================================================

    def _generate_sector_heatmap(self) -> str:
        """Heatmap de retornos por sector (11 sectores x periodos)."""
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder('Retornos Sectoriales')

        sectors_data = self._safe_val(self.data, 'sectors', 'sector_returns')
        if not sectors_data:
            return self._create_placeholder('Retornos Sectoriales — sin datos')

        # Ordenar sectores por nombre
        sector_order = [
            'technology', 'healthcare', 'financials', 'consumer_disc',
            'industrials', 'energy', 'materials', 'utilities',
            'real_estate', 'comm_services', 'consumer_staples'
        ]

        periods = ['1m', '3m', 'ytd']
        period_labels = ['1M', '3M', 'YTD']

        row_labels = []
        data_matrix = []

        for key in sector_order:
            s = sectors_data.get(key, {})
            returns = s.get('returns', {})
            if not returns:
                continue
            label = self.SECTOR_LABELS.get(key, key)
            row_labels.append(label)
            row = [returns.get(p, 0) or 0 for p in periods]
            data_matrix.append(row)

        if not row_labels:
            return self._create_placeholder('Retornos Sectoriales — sin datos')

        n_rows = len(row_labels)
        n_cols = len(period_labels)
        fig_h = max(4, 0.4 * n_rows + 1.5)
        fig, ax = plt.subplots(figsize=(6, fig_h))

        arr = np.array(data_matrix)

        # Colormap RdYlGn centrado en 0
        vmax = max(abs(arr.min()), abs(arr.max()), 1)
        im = ax.imshow(arr, cmap='RdYlGn', aspect='auto',
                       vmin=-vmax, vmax=vmax)

        ax.set_xticks(range(n_cols))
        ax.set_xticklabels(period_labels, fontsize=9, fontweight='bold')
        ax.set_yticks(range(n_rows))
        ax.set_yticklabels(row_labels, fontsize=8)

        # Anotar valores
        for i in range(n_rows):
            for j in range(n_cols):
                val = arr[i, j]
                color = 'white' if abs(val) > vmax * 0.6 else 'black'
                ax.text(j, i, f'{val:.1f}%', ha='center', va='center',
                        fontsize=7, fontweight='bold', color=color)

        ax.set_title('Retornos Sectoriales (%)', fontsize=12, fontweight='bold',
                      color=self.COLORS['primary'], pad=10)

        cbar = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
        cbar.ax.tick_params(labelsize=7)

        plt.tight_layout()
        return self._fig_to_base64(fig)

    # =========================================================================
    # 4. EARNINGS BEAT RATE — Grouped bar
    # =========================================================================

    def _generate_earnings_beat(self) -> str:
        """Beat rate y EPS growth por grupo (US, Europe, Chile)."""
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder('Earnings Beat Rate')

        earnings = self.data.get('earnings', {})
        if not earnings:
            return self._create_placeholder('Earnings Beat Rate — sin datos')

        groups = []
        beat_rates = []
        eps_growth = []

        group_order = [
            ('us_mega', 'EE.UU. Mega'),
            ('europe', 'Europa'),
            ('chile', 'Chile')
        ]

        has_data = False
        for key, label in group_order:
            g = earnings.get(key, {})
            br = g.get('avg_beat_rate')
            eg = g.get('avg_eps_growth_yoy')
            groups.append(label)
            beat_rates.append(br if br is not None else 0)
            eps_growth.append(eg if eg is not None else 0)
            if br is not None or eg is not None:
                has_data = True

        if not has_data:
            return self._create_placeholder('Earnings Beat Rate — sin datos')

        n = len(groups)
        fig, ax = plt.subplots(figsize=(7, 4))

        x = np.arange(n)
        bar_w = 0.35

        bars_br = ax.bar(x - bar_w / 2, beat_rates, bar_w, label='Beat Rate (%)',
                         color=self.SERIES_COLORS[0], alpha=0.85)
        bars_eg = ax.bar(x + bar_w / 2, eps_growth, bar_w, label='EPS Growth YoY (%)',
                         color=self.SERIES_COLORS[1], alpha=0.85)

        # Anotaciones
        for bar, val in zip(bars_br, beat_rates):
            if val != 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                        f'{val:.0f}%', ha='center', va='bottom', fontsize=8,
                        fontweight='bold', color=self.COLORS['text_dark'])
        for bar, val in zip(bars_eg, eps_growth):
            if val != 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                        f'{val:.1f}%', ha='center', va='bottom', fontsize=8,
                        fontweight='bold', color=self.COLORS['text_dark'])

        # Linea referencia 75% beat rate
        ax.axhline(y=75, color=self.COLORS['text_light'], linewidth=1,
                   linestyle=':', alpha=0.7, label='Promedio histórico beat rate (75%)')

        ax.set_xticks(x)
        ax.set_xticklabels(groups, fontsize=10)
        ax.set_ylabel('%', fontsize=9)
        ax.set_title('Earnings: Beat Rate y Crecimiento EPS', fontsize=12,
                      fontweight='bold', color=self.COLORS['primary'], pad=10)
        ax.legend(loc='upper right', fontsize=7)
        plt.tight_layout()
        return self._fig_to_base64(fig)

    # =========================================================================
    # 5. STYLE BOX — Growth vs Value, Large vs Small
    # =========================================================================

    def _generate_style_box(self) -> str:
        """Retornos Growth vs Value y Large vs Small por periodo."""
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder('Style Box')

        style = self.data.get('style', {})
        if not style:
            return self._create_placeholder('Style Box — sin datos')

        growth_ret = self._safe_val(style, 'growth', 'returns', default={})
        value_ret = self._safe_val(style, 'value', 'returns', default={})
        large_ret = self._safe_val(style, 'large_cap', 'returns', default={})
        small_ret = self._safe_val(style, 'small_cap', 'returns', default={})

        if not growth_ret and not value_ret:
            return self._create_placeholder('Style Box — sin datos')

        periods = ['1m', '3m', 'ytd']
        period_labels = ['1M', '3M', 'YTD']

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 4))

        # Panel 1: Growth vs Value
        x = np.arange(len(periods))
        bar_w = 0.35
        g_vals = [growth_ret.get(p, 0) or 0 for p in periods]
        v_vals = [value_ret.get(p, 0) or 0 for p in periods]

        ax1.bar(x - bar_w / 2, g_vals, bar_w, label='Growth (IWF)',
                color='#805ad5', alpha=0.85)
        ax1.bar(x + bar_w / 2, v_vals, bar_w, label='Value (IWD)',
                color=self.SERIES_COLORS[1], alpha=0.85)

        # Anotaciones spread
        spread = self._safe_val(style, 'growth_value_spread', default={})
        for i, p in enumerate(periods):
            sp = spread.get(p, 0) or 0
            y_pos = max(g_vals[i], v_vals[i]) + 0.5
            if sp != 0:
                color = '#805ad5' if sp > 0 else self.SERIES_COLORS[1]
                ax1.text(i, y_pos, f'Δ{sp:+.1f}pp', ha='center',
                         fontsize=7, color=color, fontweight='bold')

        ax1.set_xticks(x)
        ax1.set_xticklabels(period_labels, fontsize=9)
        ax1.set_ylabel('Retorno (%)', fontsize=8)
        ax1.set_title('Growth vs Value', fontsize=11, fontweight='bold',
                       color=self.COLORS['primary'])
        ax1.legend(fontsize=7, loc='best')
        ax1.axhline(y=0, color=self.COLORS['primary'], linewidth=0.5)

        # Panel 2: Large vs Small
        l_vals = [large_ret.get(p, 0) or 0 for p in periods]
        s_vals = [small_ret.get(p, 0) or 0 for p in periods]

        ax2.bar(x - bar_w / 2, l_vals, bar_w, label='Large Cap (IWB)',
                color=self.SERIES_COLORS[0], alpha=0.85)
        ax2.bar(x + bar_w / 2, s_vals, bar_w, label='Small Cap (IWM)',
                color=self.SERIES_COLORS[2], alpha=0.85)

        size_spread = self._safe_val(style, 'size_spread', default={})
        for i, p in enumerate(periods):
            sp = size_spread.get(p, 0) or 0
            y_pos = max(l_vals[i], s_vals[i]) + 0.5
            if sp != 0:
                color = self.SERIES_COLORS[2] if sp > 0 else self.SERIES_COLORS[0]
                ax2.text(i, y_pos, f'Δ{sp:+.1f}pp', ha='center',
                         fontsize=7, color=color, fontweight='bold')

        ax2.set_xticks(x)
        ax2.set_xticklabels(period_labels, fontsize=9)
        ax2.set_ylabel('Retorno (%)', fontsize=8)
        ax2.set_title('Large vs Small Cap', fontsize=11, fontweight='bold',
                       color=self.COLORS['primary'])
        ax2.legend(fontsize=7, loc='best')
        ax2.axhline(y=0, color=self.COLORS['primary'], linewidth=0.5)

        plt.tight_layout()
        return self._fig_to_base64(fig)

    # =========================================================================
    # 6. CORRELATION MATRIX — Lower triangular heatmap
    # =========================================================================

    def _generate_correlation_matrix(self) -> str:
        """Matriz de correlacion 10x10 con mascara triangular."""
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder('Matriz de Correlación')

        corr_data = self._safe_val(self.data, 'risk', 'correlation_matrix')
        if not corr_data:
            return self._create_placeholder('Matriz de Correlación — sin datos')

        # Orden preferido de tickers
        ticker_order = ['SPY', 'EFA', 'EEM', 'EWJ', 'ECH', 'EWZ', 'MCHI', 'GLD', 'TLT', 'HYG']
        tickers = [t for t in ticker_order if t in corr_data]

        if len(tickers) < 3:
            return self._create_placeholder('Matriz de Correlación — datos insuficientes')

        n = len(tickers)
        matrix = np.zeros((n, n))
        for i, t1 in enumerate(tickers):
            for j, t2 in enumerate(tickers):
                matrix[i, j] = corr_data.get(t1, {}).get(t2, 0)

        # Mascara triangular superior
        mask = np.triu(np.ones_like(matrix, dtype=bool), k=1)

        fig, ax = plt.subplots(figsize=(7, 6))

        masked = np.ma.array(matrix, mask=mask)
        im = ax.imshow(masked, cmap='RdYlBu_r', aspect='auto',
                       vmin=-0.2, vmax=1.0)

        ax.set_xticks(range(n))
        ax.set_xticklabels(tickers, fontsize=8, rotation=45, ha='right')
        ax.set_yticks(range(n))
        ax.set_yticklabels(tickers, fontsize=8)

        # Anotar valores (solo triangular inferior + diagonal)
        for i in range(n):
            for j in range(n):
                if not mask[i, j]:
                    val = matrix[i, j]
                    color = 'white' if abs(val) > 0.6 else 'black'
                    ax.text(j, i, f'{val:.2f}', ha='center', va='center',
                            fontsize=6, fontweight='bold', color=color)

        ax.set_title('Matriz de Correlación (6M)', fontsize=12, fontweight='bold',
                      color=self.COLORS['primary'], pad=10)

        cbar = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
        cbar.ax.tick_params(labelsize=7)

        # Ocultar celdas de la mascara
        for i in range(n):
            for j in range(n):
                if mask[i, j]:
                    ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1,
                                               fill=True, facecolor='white',
                                               edgecolor='white'))

        plt.tight_layout()
        return self._fig_to_base64(fig)

    # =========================================================================
    # 7. VIX RANGE — Bullet/gauge chart
    # =========================================================================

    def _generate_vix_range(self) -> str:
        """VIX actual vs rango 1Y con zonas coloreadas."""
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder('VIX Range')

        vix_data = self._safe_val(self.data, 'risk', 'vix')
        if not vix_data:
            return self._create_placeholder('VIX Range — sin datos')

        current = vix_data.get('current')
        avg_1y = vix_data.get('avg_1y')
        high_1y = vix_data.get('high_1y')
        low_1y = vix_data.get('low_1y')

        if current is None:
            return self._create_placeholder('VIX Range — sin datos')

        fig, ax = plt.subplots(figsize=(8, 2.5))

        # Rango del chart
        chart_min = 0
        chart_max = max(45, (high_1y or 40) * 1.1)

        # Zonas coloreadas
        zones = [
            (0, 15, '#c6f6d5', 'Baja\nvol'),
            (15, 20, '#fefcbf', 'Normal'),
            (20, 25, '#fed7aa', 'Elevada'),
            (25, chart_max, '#fed7d7', 'Alta\nvol'),
        ]
        bar_h = 0.6
        for x_start, x_end, color, label in zones:
            ax.barh(0, x_end - x_start, bar_h, left=x_start,
                    color=color, edgecolor='none')
            mid = (x_start + x_end) / 2
            if x_end <= chart_max:
                ax.text(mid, -0.55, label, ha='center', va='top',
                        fontsize=7, color=self.COLORS['text_light'])

        # Rango 1Y (linea)
        if low_1y is not None and high_1y is not None:
            ax.plot([low_1y, high_1y], [0, 0], color=self.COLORS['primary'],
                    linewidth=2, alpha=0.5, zorder=3)
            ax.plot(low_1y, 0, '|', color=self.COLORS['primary'],
                    markersize=15, zorder=3)
            ax.plot(high_1y, 0, '|', color=self.COLORS['primary'],
                    markersize=15, zorder=3)

        # Promedio 1Y
        if avg_1y is not None:
            ax.plot(avg_1y, 0, 'D', color=self.COLORS['accent'],
                    markersize=8, zorder=4, label=f'Avg 1Y: {avg_1y:.1f}')

        # VIX actual (marcador principal)
        marker_color = (self.COLORS['positive'] if current < 20
                       else self.COLORS['neutral'] if current < 25
                       else self.COLORS['negative'])
        ax.plot(current, 0, 'v', color=marker_color, markersize=14,
                zorder=5, label=f'VIX actual: {current:.1f}')
        ax.text(current, 0.45, f'{current:.1f}', ha='center', va='bottom',
                fontsize=11, fontweight='bold', color=marker_color)

        ax.set_xlim(chart_min, chart_max)
        ax.set_ylim(-1, 1)
        ax.set_yticks([])
        ax.spines['left'].set_visible(False)
        ax.set_xlabel('VIX Index', fontsize=9)
        ax.set_title('VIX: Nivel Actual vs Rango 1 Año', fontsize=12,
                      fontweight='bold', color=self.COLORS['primary'], pad=10)
        ax.legend(loc='upper right', fontsize=8)

        plt.tight_layout()
        return self._fig_to_base64(fig)


    # =========================================================================
    # 8. CHILE IPSA vs COBRE — Dual axis time series
    # =========================================================================

    def _generate_chile_ipsa_copper(self) -> str:
        """IPSA vs Cobre: correlación Chile-commodities (datos BCCh)."""
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder('IPSA vs Cobre')

        bcch = self.data.get('bcch_indices', {})
        ipsa = bcch.get('ipsa', {})
        copper = bcch.get('copper', {})

        if not ipsa or not copper or 'error' in ipsa or 'error' in copper:
            return self._create_placeholder('IPSA vs Cobre — sin datos BCCh')

        # Build comparison from available return periods
        periods = ['1y', '3m', '1m']
        period_labels = ['1A', '3M', '1M', 'Actual']
        ipsa_vals = []
        copper_vals = []
        labels_used = []

        for p in periods:
            i_ret = ipsa.get('returns', {}).get(p)
            c_ret = copper.get('returns', {}).get(p)
            if i_ret is not None and c_ret is not None:
                ipsa_vals.append(i_ret)
                copper_vals.append(c_ret)
                labels_used.append({'1y': '1A', '3m': '3M', '1m': '1M'}[p])

        if not labels_used:
            return self._create_placeholder('IPSA vs Cobre — sin retornos')

        fig, ax1 = plt.subplots(figsize=(7, 4))

        x = np.arange(len(labels_used))
        bar_w = 0.35

        bars1 = ax1.bar(x - bar_w / 2, ipsa_vals, bar_w, label='IPSA',
                        color=self.SERIES_COLORS[0], alpha=0.85)
        bars2 = ax1.bar(x + bar_w / 2, copper_vals, bar_w, label='Cobre',
                        color=self.COLORS['accent'], alpha=0.85)

        # Annotations
        for bars in [bars1, bars2]:
            for bar in bars:
                h = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width() / 2, h + (0.3 if h >= 0 else -0.8),
                         f'{h:+.1f}%', ha='center', va='bottom' if h >= 0 else 'top',
                         fontsize=7, fontweight='bold', color=self.COLORS['text_medium'])

        ax1.set_xticks(x)
        ax1.set_xticklabels(labels_used, fontsize=9)
        ax1.set_ylabel('Retorno (%)', fontsize=9)
        ax1.axhline(y=0, color=self.COLORS['primary'], linewidth=0.5)
        ax1.set_title('IPSA vs Cobre — Retornos Comparados', fontsize=12,
                       fontweight='bold', color=self.COLORS['primary'], pad=10)
        ax1.legend(loc='best', fontsize=8)

        # Add current levels as text
        ipsa_val = ipsa.get('value')
        copper_val = copper.get('value')
        note_parts = []
        if ipsa_val:
            note_parts.append(f'IPSA: {ipsa_val:,.0f}')
        if copper_val:
            note_parts.append(f'Cobre: {copper_val:.2f} USc/lb')
        if note_parts:
            ax1.text(0.5, -0.15, ' | '.join(note_parts), transform=ax1.transAxes,
                     ha='center', fontsize=8, color=self.COLORS['text_light'])

        plt.tight_layout()
        return self._fig_to_base64(fig)

    # =========================================================================
    # 9. CREDIT RISK — IG vs HY Spreads
    # =========================================================================

    def _generate_credit_risk(self) -> str:
        """IG vs HY spreads con percentiles y VIX."""
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder('Credit Risk Spreads')

        credit = self.data.get('credit', {})
        risk = self.data.get('risk', {})

        if not credit or 'error' in credit:
            return self._create_placeholder('Credit Risk — sin datos')

        ig = credit.get('ig_spread')
        hy = credit.get('hy_spread')
        ig_pct = credit.get('ig_percentile')
        hy_pct = credit.get('hy_percentile')
        vix = self._safe_val(risk, 'vix', 'current')

        if ig is None and hy is None:
            return self._create_placeholder('Credit Risk — sin spreads')

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 4))

        # Panel 1: Spread levels
        labels = []
        spreads = []
        colors = []
        if ig is not None:
            labels.append('IG')
            spreads.append(ig)
            colors.append(self.SERIES_COLORS[0])
        if hy is not None:
            labels.append('HY')
            spreads.append(hy)
            colors.append(self.COLORS['accent'])

        bars = ax1.bar(labels, spreads, color=colors, alpha=0.85, width=0.5)
        for bar, val in zip(bars, spreads):
            ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 5,
                     f'{val:.0f}bp', ha='center', va='bottom',
                     fontsize=10, fontweight='bold', color=self.COLORS['text_dark'])

        ax1.set_ylabel('Spread (bps)', fontsize=9)
        ax1.set_title('Spreads de Crédito', fontsize=11, fontweight='bold',
                       color=self.COLORS['primary'])

        # Panel 2: Percentiles + VIX
        pct_labels = []
        pct_vals = []
        pct_colors = []
        if ig_pct is not None:
            pct_labels.append('IG %ile')
            pct_vals.append(ig_pct)
            pct_colors.append(self.SERIES_COLORS[0])
        if hy_pct is not None:
            pct_labels.append('HY %ile')
            pct_vals.append(hy_pct)
            pct_colors.append(self.COLORS['accent'])
        if vix is not None:
            pct_labels.append('VIX')
            pct_vals.append(vix)
            pct_colors.append(self.COLORS['negative'])

        if pct_labels:
            bars2 = ax2.bar(pct_labels, pct_vals, color=pct_colors, alpha=0.85, width=0.5)
            for bar, val in zip(bars2, pct_vals):
                ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                         f'{val:.0f}', ha='center', va='bottom',
                         fontsize=10, fontweight='bold', color=self.COLORS['text_dark'])

        ax2.set_title('Percentiles 5A y VIX', fontsize=11, fontweight='bold',
                       color=self.COLORS['primary'])

        # Reference lines
        if any('ile' in l for l in pct_labels):
            ax2.axhline(y=50, color=self.COLORS['text_light'], linewidth=1,
                        linestyle=':', alpha=0.5, label='Mediana')
            ax2.legend(fontsize=7)

        fig.suptitle('Condiciones de Crédito para Equity', fontsize=12,
                      fontweight='bold', color=self.COLORS['primary'], y=1.02)
        plt.tight_layout()
        return self._fig_to_base64(fig)

    # =========================================================================
    # 10. DRAWDOWN — Current drawdown S&P 500 / portfolio
    # =========================================================================

    def _generate_drawdown(self) -> str:
        """Drawdown actual y máximo del portfolio equity."""
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder('Drawdown Analysis')

        risk = self.data.get('risk', {})
        if not risk or 'error' in risk:
            return self._create_placeholder('Drawdown — sin datos')

        max_dd = risk.get('max_drawdown')
        curr_dd = risk.get('current_drawdown')
        var_95 = risk.get('var_95_daily')
        var_99 = risk.get('var_99_daily')
        div_score = risk.get('diversification_score')

        if max_dd is None and curr_dd is None:
            return self._create_placeholder('Drawdown — sin datos')

        fig, ax = plt.subplots(figsize=(8, 3.5))

        # Metrics as horizontal bars
        metrics = []
        values = []
        colors = []

        if curr_dd is not None:
            metrics.append('Drawdown\nActual')
            values.append(abs(curr_dd))
            colors.append(self.COLORS['accent'] if abs(curr_dd) < 10 else self.COLORS['negative'])
        if max_dd is not None:
            metrics.append('Max\nDrawdown')
            values.append(abs(max_dd))
            colors.append(self.COLORS['negative'])
        if var_95 is not None:
            metrics.append('VaR 95%\n(Diario)')
            values.append(abs(var_95))
            colors.append(self.SERIES_COLORS[0])
        if var_99 is not None:
            metrics.append('VaR 99%\n(Diario)')
            values.append(abs(var_99))
            colors.append('#805ad5')

        if not metrics:
            return self._create_placeholder('Drawdown — sin métricas')

        y = np.arange(len(metrics))
        bars = ax.barh(y, values, color=colors, alpha=0.85, height=0.5)

        for bar, val in zip(bars, values):
            ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                    f'{val:.2f}%', va='center', fontsize=9, fontweight='bold',
                    color=self.COLORS['text_dark'])

        ax.set_yticks(y)
        ax.set_yticklabels(metrics, fontsize=9)
        ax.set_xlabel('Pérdida (%)', fontsize=9)
        ax.set_title('Métricas de Riesgo — Portfolio Equity', fontsize=12,
                      fontweight='bold', color=self.COLORS['primary'], pad=10)

        if div_score is not None:
            ax.text(0.98, 0.02, f'Diversificación: {div_score:.2f}',
                    transform=ax.transAxes, ha='right', va='bottom',
                    fontsize=8, color=self.COLORS['text_light'],
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))

        ax.invert_yaxis()
        plt.tight_layout()
        return self._fig_to_base64(fig)

    # =========================================================================
    # 11. FACTOR RADAR — Factor scores por region
    # =========================================================================

    def _generate_factor_radar(self) -> str:
        """Factor scores (momentum, value, quality, growth) por ETF regional."""
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder('Factor Performance')

        factors = self.data.get('factors', {})
        if not factors or 'error' in factors:
            return self._create_placeholder('Factor Performance — sin datos')

        # Collect data for each ticker that has factor scores
        ticker_order = ['SPY', 'EFA', 'EEM', 'EWJ', 'ECH']
        factor_names = ['momentum', 'value', 'growth', 'quality']
        factor_labels = ['Momentum', 'Value', 'Growth', 'Quality']

        tickers_with_data = []
        data_rows = []

        for ticker in ticker_order:
            f = factors.get(ticker, {})
            if 'error' in f or not isinstance(f, dict):
                continue
            scores = [f.get(fn) for fn in factor_names]
            if any(s is not None for s in scores):
                tickers_with_data.append(self.REGION_LABELS.get(
                    {'SPY': 'us', 'EFA': 'europe', 'EEM': 'em', 'EWJ': 'japan', 'ECH': 'chile'}.get(ticker, ''), ticker))
                data_rows.append([s if s is not None else 0 for s in scores])

        if not tickers_with_data:
            return self._create_placeholder('Factor Performance — sin scores')

        fig, ax = plt.subplots(figsize=(8, max(3, 0.6 * len(tickers_with_data) + 1.5)))

        n_tickers = len(tickers_with_data)
        n_factors = len(factor_labels)
        y = np.arange(n_tickers)
        bar_h = 0.8 / n_factors

        for i, (fname, flabel) in enumerate(zip(factor_names, factor_labels)):
            vals = [row[i] for row in data_rows]
            offset = (i - n_factors / 2 + 0.5) * bar_h
            bars = ax.barh(y + offset, vals, bar_h,
                          label=flabel, color=self.SERIES_COLORS[i % len(self.SERIES_COLORS)],
                          alpha=0.85)
            for bar in bars:
                w = bar.get_width()
                if w > 5:
                    ax.text(w + 1, bar.get_y() + bar.get_height() / 2,
                            f'{w:.0f}', va='center', fontsize=6,
                            color=self.COLORS['text_medium'])

        ax.set_yticks(y)
        ax.set_yticklabels(tickers_with_data, fontsize=9)
        ax.set_xlabel('Score (0-100)', fontsize=9)
        ax.set_title('Factor Scores por Región', fontsize=12, fontweight='bold',
                      color=self.COLORS['primary'], pad=10)
        ax.legend(loc='lower right', fontsize=7, ncol=2)
        ax.set_xlim(0, 100)
        plt.tight_layout()
        return self._fig_to_base64(fig)

    # =========================================================================
    # 12. EARNINGS REVISIONS — Upgrades vs Downgrades
    # =========================================================================

    def _generate_earnings_revisions(self) -> str:
        """Revision trends: upgrade % vs downgrade % por grupo."""
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder('Earnings Revisions')

        earnings = self.data.get('earnings', {})
        if not earnings or 'error' in earnings:
            return self._create_placeholder('Earnings Revisions — sin datos')

        group_order = [
            ('us_mega', 'EE.UU. Mega'),
            ('europe', 'Europa'),
            ('chile', 'Chile'),
        ]

        groups = []
        upgrades = []
        downgrades = []
        has_data = False

        for key, label in group_order:
            g = earnings.get(key, {})
            up = g.get('avg_upgrade_pct_30d')
            down = g.get('avg_revision_down_30d')
            # Also try individual stock-level aggregation
            if up is None:
                stocks = g.get('stocks', [])
                up_vals = [s.get('upgrade_pct_30d') for s in stocks if s.get('upgrade_pct_30d') is not None]
                up = round(sum(up_vals) / len(up_vals), 1) if up_vals else None
            if down is None:
                stocks = g.get('stocks', [])
                dn_vals = [s.get('revision_down_30d') for s in stocks if s.get('revision_down_30d') is not None]
                down = round(sum(dn_vals) / len(dn_vals), 1) if dn_vals else None

            groups.append(label)
            upgrades.append(up if up is not None else 0)
            downgrades.append(down if down is not None else 0)
            if up is not None or down is not None:
                has_data = True

        if not has_data:
            return self._create_placeholder('Earnings Revisions — sin datos')

        fig, ax = plt.subplots(figsize=(7, 4))

        x = np.arange(len(groups))
        bar_w = 0.35

        bars_up = ax.bar(x - bar_w / 2, upgrades, bar_w, label='Upgrades 30d',
                         color=self.COLORS['positive'], alpha=0.85)
        bars_dn = ax.bar(x + bar_w / 2, downgrades, bar_w, label='Downgrades 30d',
                         color=self.COLORS['negative'], alpha=0.85)

        for bar, val in zip(bars_up, upgrades):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                        f'{val:.0f}', ha='center', va='bottom', fontsize=9,
                        fontweight='bold', color=self.COLORS['positive'])
        for bar, val in zip(bars_dn, downgrades):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                        f'{val:.0f}', ha='center', va='bottom', fontsize=9,
                        fontweight='bold', color=self.COLORS['negative'])

        ax.set_xticks(x)
        ax.set_xticklabels(groups, fontsize=10)
        ax.set_ylabel('Cantidad', fontsize=9)
        ax.set_title('Revisiones de Earnings (30 días)', fontsize=12,
                      fontweight='bold', color=self.COLORS['primary'], pad=10)
        ax.legend(loc='upper right', fontsize=8)
        plt.tight_layout()
        return self._fig_to_base64(fig)


# =============================================================================
# CLI para testing
# =============================================================================

if __name__ == '__main__':
    import json
    import sys
    from pathlib import Path

    sys.stdout.reconfigure(encoding='utf-8')

    # Buscar equity data mas reciente
    equity_dir = Path(__file__).parent / "output" / "equity_data"
    equity_files = sorted(equity_dir.glob("equity_data_*.json"), reverse=True)

    if equity_files:
        print(f"[INFO] Cargando: {equity_files[0].name}")
        with open(equity_files[0], 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        print("[WARN] Sin equity data — usando dict vacio")
        data = {}

    gen = RVChartsGenerator(data)
    charts = gen.generate_all_charts()

    print(f"\nCharts generados: {len(charts)}")
    for k, v in charts.items():
        is_img = v.startswith('data:image') if v else False
        size = len(v) if v else 0
        print(f"  {k}: {size:,} chars, es_imagen={is_img}")
