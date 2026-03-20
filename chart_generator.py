# -*- coding: utf-8 -*-
"""
Greybark Research - Chart Generator
=====================================

Genera charts profesionales para los reportes.
Los charts se generan como SVG inline o PNG base64 para embedding en HTML.

Dependencias:
- matplotlib
- numpy
"""

import base64
import io
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import warnings

logger = logging.getLogger(__name__)


class ChartDataError(Exception):
    """Raised when a chart cannot be generated due to missing data."""
    pass


# Suprimir warnings de matplotlib
warnings.filterwarnings('ignore')

try:
    import matplotlib
    matplotlib.use('Agg')  # Backend sin GUI
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.ticker import FuncFormatter
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: matplotlib not installed. Charts will use fallback placeholders.")


class ChartGenerator:
    """Generador de charts para reportes."""

    # Colores Greybark (consistente con CSS — escala de negros)
    COLORS = {
        'primary_blue': '#1a1a1a',
        'secondary_blue': '#3a3a3a',
        'accent_orange': '#dd6b20',
        'positive': '#276749',
        'negative': '#c53030',
        'neutral': '#744210',
        'bg_light': '#f7f7f7',
        'text_dark': '#1a1a1a',
        'text_medium': '#4a4a4a',
        'text_light': '#718096',
    }

    # Paleta para series multiples
    SERIES_COLORS = [
        '#1a365d',  # Dark blue
        '#dd6b20',  # Orange
        '#276749',  # Green
        '#c53030',  # Red
        '#805ad5',  # Purple
        '#d69e2e',  # Gold
        '#319795',  # Teal
        '#e53e3e',  # Light red
    ]

    @staticmethod
    def _safe_float(val, default: float = 0.0) -> float:
        """Safely convert a value to float, handling 'N/D', '%', '+' etc."""
        if val is None:
            return default
        s = str(val).replace('%', '').replace('+', '').replace(' a/a', '').strip()
        if not s or s in ('N/D', 'N/A', '-', '--'):
            return default
        try:
            return float(s)
        except (ValueError, TypeError):
            return default

    def __init__(self, width: int = 8, height: int = 4, dpi: int = 100):
        self.width = width
        self.height = height
        self.dpi = dpi
        self._setup_style()

    def _setup_style(self):
        """Configura el estilo global de matplotlib."""
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
        """Convierte figura matplotlib a base64 PNG."""
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=self.dpi, bbox_inches='tight',
                   facecolor='white', edgecolor='none')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        return f"data:image/png;base64,{img_base64}"

    def _legend_label(self, label: str, values: List[float]) -> str:
        """Genera label de leyenda con promedio y ultimo dato."""
        avg = sum(values) / len(values)
        last = values[-1]
        # Formatear segun magnitud
        if abs(avg) >= 100:
            return f"{label}  (Prom: {avg:,.0f} | Ult: {last:,.0f})"
        else:
            return f"{label}  (Prom: {avg:.1f} | Ult: {last:.1f})"

    def _create_placeholder(self, title: str) -> str:
        """Crea placeholder HTML cuando matplotlib no esta disponible."""
        return f'''
        <div style="background: #f7fafc; border: 2px dashed #e2e8f0;
                    border-radius: 8px; padding: 40px; text-align: center;
                    color: #718096; margin: 15px 0;">
            <div style="font-size: 14pt; margin-bottom: 10px;">{title}</div>
            <div style="font-size: 10pt;">Chart no disponible - instale matplotlib</div>
        </div>
        '''

    # =========================================================================
    # YIELD CURVE
    # =========================================================================

    def _maturity_to_years(self, maturity: str) -> float:
        """Convierte string de maturity a años (ej: '3M' -> 0.25, '10Y' -> 10)."""
        if maturity.endswith('M'):
            return float(maturity[:-1]) / 12
        elif maturity.endswith('Y'):
            return float(maturity[:-1])
        return 0

    def generate_yield_curve(self,
                             current: Dict[str, float],
                             previous_month: Dict[str, float] = None,
                             previous_year: Dict[str, float] = None,
                             title: str = "US Treasury Yield Curve") -> str:
        """
        Genera chart de yield curve con escala proporcional al tiempo.

        Args:
            current: Dict con maturities como keys y yields como values
                     Ej: {'3M': 4.5, '2Y': 4.2, '5Y': 4.0, '10Y': 4.1, '30Y': 4.3}
            previous_month: Curva del mes anterior para comparación
            previous_year: Curva de hace 1 año para comparación
            title: Titulo del chart
        """
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder(title)

        fig, ax = plt.subplots(figsize=(self.width, self.height + 0.5))

        # Ordenar maturities
        maturity_order = ['1M', '3M', '6M', '1Y', '2Y', '3Y', '5Y', '7Y', '10Y', '20Y', '30Y']
        maturities = [m for m in maturity_order if m in current]
        yields_current = [current[m] for m in maturities]

        # Convertir maturities a años para escala proporcional
        x_years = [self._maturity_to_years(m) for m in maturities]

        # Plot curva de 1 año atras (primero, para que quede atras)
        if previous_year:
            yields_year = [previous_year.get(m, None) for m in maturities]
            x_year = [x_years[i] for i, y in enumerate(yields_year) if y is not None]
            yields_year_clean = [y for y in yields_year if y is not None]
            ax.plot(x_year, yields_year_clean, 's--', color=self.COLORS['negative'],
                   linewidth=1.5, markersize=5, label='Hace 1 Ano', alpha=0.5)

        # Plot curva mes anterior
        if previous_month:
            yields_prev = [previous_month.get(m, None) for m in maturities]
            x_prev = [x_years[i] for i, y in enumerate(yields_prev) if y is not None]
            yields_prev_clean = [y for y in yields_prev if y is not None]
            ax.plot(x_prev, yields_prev_clean, 'o--', color=self.COLORS['text_light'],
                   linewidth=1.5, markersize=6, label='Mes Anterior', alpha=0.7)

        # Plot curva actual (ultimo, para que quede al frente)
        ax.plot(x_years, yields_current, 'o-', color=self.COLORS['primary_blue'],
                linewidth=2.5, markersize=8, label='Actual')

        # Formateo - mostrar solo maturities clave en eje X
        key_maturities_x = ['3M', '1Y', '2Y', '5Y', '10Y', '30Y']  # Sin 6M
        x_ticks = [x for x, m in zip(x_years, maturities) if m in key_maturities_x]
        x_labels = [m for m in maturities if m in key_maturities_x]
        ax.set_xticks(x_ticks)
        ax.set_xticklabels(x_labels, fontsize=9)
        ax.set_ylabel('Yield (%)', fontweight='bold')
        ax.set_xlabel('Maturity', fontweight='bold')
        ax.set_title(title, fontsize=12, fontweight='bold', color=self.COLORS['primary_blue'])

        # Agregar valores solo en puntos clave para evitar traslape
        key_maturities = ['3M', '2Y', '10Y', '30Y']  # Solo estos

        for i, (mat, x_pos, y) in enumerate(zip(maturities, x_years, yields_current)):
            if mat not in key_maturities:
                continue

            # Posicion: corto plazo arriba, largo plazo abajo
            if x_pos < 3:  # Menos de 3 años
                offset = (0, 18)
                va = 'bottom'
            else:
                offset = (0, -18)
                va = 'top'

            ax.annotate(f'{y:.2f}%',
                       xy=(x_pos, y),
                       xytext=offset,
                       textcoords="offset points",
                       ha='center',
                       va=va,
                       fontsize=9,
                       fontweight='bold',
                       color=self.COLORS['primary_blue'],
                       bbox=dict(boxstyle='round,pad=0.2', facecolor='white',
                                edgecolor=self.COLORS['primary_blue'], alpha=0.9),
                       arrowprops=dict(arrowstyle='->', color=self.COLORS['primary_blue'],
                                      lw=1, alpha=0.7))

        ax.legend(loc='upper right', framealpha=0.9, fontsize=8)

        # Ajustar limites Y para dar espacio a las etiquetas
        y_min = min(yields_current)
        y_max = max(yields_current)
        if previous_year:
            y_min = min(y_min, min([y for y in previous_year.values()]))
            y_max = max(y_max, max([y for y in previous_year.values()]))
        ax.set_ylim(y_min - 0.6, y_max + 0.6)

        # Limites X para que se vea bien
        ax.set_xlim(-0.5, max(x_years) + 1)

        plt.tight_layout()
        return self._fig_to_base64(fig)

    # =========================================================================
    # GDP COMPARISON BAR CHART
    # =========================================================================

    def generate_gdp_comparison(self,
                                data: List[Dict[str, Any]],
                                title: str = "GDP Growth Comparison") -> str:
        """
        Genera bar chart comparando GDP por region.

        Args:
            data: Lista de dicts con 'region', 'actual', 'forecast', 'consenso'
        """
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder(title)

        fig, ax = plt.subplots(figsize=(self.width, self.height))

        regions = [d['region'] for d in data]
        actual = [self._safe_float(d['actual']) for d in data]
        forecast = [self._safe_float(d['forecast']) for d in data]
        consenso = [self._safe_float(d['consenso']) for d in data]

        x = np.arange(len(regions))
        width = 0.25

        bars1 = ax.bar(x - width, actual, width, label='2025',
                       color=self.COLORS['text_light'], alpha=0.7)
        bars2 = ax.bar(x, forecast, width, label='2026F Greybark',
                       color=self.COLORS['primary_blue'])
        bars3 = ax.bar(x + width, consenso, width, label='2026F Consenso',
                       color=self.COLORS['accent_orange'], alpha=0.8)

        ax.set_ylabel('GDP Growth (%)', fontweight='bold')
        ax.set_title(title, fontsize=12, fontweight='bold', color=self.COLORS['primary_blue'])
        ax.set_xticks(x)
        ax.set_xticklabels(regions, fontweight='bold')
        ax.legend(loc='upper right')

        # Agregar valores sobre barras
        for bars in [bars1, bars2, bars3]:
            for bar in bars:
                height = bar.get_height()
                ax.annotate(f'{height:.1f}%',
                           xy=(bar.get_x() + bar.get_width() / 2, height),
                           xytext=(0, 3), textcoords="offset points",
                           ha='center', va='bottom', fontsize=7)

        ax.axhline(y=0, color='black', linewidth=0.5)
        plt.tight_layout()
        return self._fig_to_base64(fig)

    # =========================================================================
    # INFLATION DECOMPOSITION
    # =========================================================================

    def generate_inflation_decomposition(self,
                                         components: List[Dict[str, Any]],
                                         title: str = "US Inflation Decomposition") -> str:
        """
        Genera horizontal bar chart de componentes de inflación.

        Args:
            components: Lista de dicts con 'nombre', 'valor', 'tendencia'
        """
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder(title)

        fig, ax = plt.subplots(figsize=(self.width, self.height))

        names = [c['nombre'] for c in components]
        values = [self._safe_float(c['valor']) for c in components]

        # Colores basados en valor
        colors = []
        for v in values:
            if v > 3:
                colors.append(self.COLORS['negative'])
            elif v > 2:
                colors.append(self.COLORS['neutral'])
            elif v >= 0:
                colors.append(self.COLORS['positive'])
            else:
                colors.append(self.COLORS['secondary_blue'])

        y_pos = np.arange(len(names))
        bars = ax.barh(y_pos, values, color=colors, height=0.6)

        ax.set_yticks(y_pos)
        ax.set_yticklabels(names)
        ax.set_xlabel('YoY Change (%)', fontweight='bold')
        ax.set_title(title, fontsize=12, fontweight='bold', color=self.COLORS['primary_blue'])

        # Linea de target 2%
        ax.axvline(x=2, color=self.COLORS['accent_orange'], linestyle='--',
                   linewidth=2, label='Fed Target (2%)')

        # Valores en las barras
        for bar, val in zip(bars, values):
            width = bar.get_width()
            label_x = width + 0.1 if width >= 0 else width - 0.3
            ax.annotate(f'{val:.1f}%', xy=(label_x, bar.get_y() + bar.get_height()/2),
                       va='center', fontsize=9, fontweight='bold')

        ax.legend(loc='upper right')
        ax.set_xlim(min(values) - 1, max(values) + 1)

        plt.tight_layout()
        return self._fig_to_base64(fig)

    # =========================================================================
    # FED FUNDS PATH
    # =========================================================================

    def generate_fed_path(self,
                          historical: List[Tuple[str, float]],
                          projections: Dict[str, Dict],
                          title: str = "Fed Funds Rate Path") -> str:
        """
        Genera chart de trayectoria Fed Funds.

        Args:
            historical: Lista de (fecha, rate)
            projections: Dict con años y rangos {mediana, rango}
        """
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder(title)

        fig, ax = plt.subplots(figsize=(self.width, self.height))

        # Datos históricos
        dates = [h[0] for h in historical]
        rates = [h[1] for h in historical]

        ax.plot(range(len(dates)), rates, 'o-', color=self.COLORS['primary_blue'],
               linewidth=2, markersize=6, label='Fed Funds Rate')

        # Proyecciónes
        proj_start = len(dates)
        proj_labels = list(projections.keys())
        proj_medianas = [self._safe_float(projections[k]['mediana']) for k in proj_labels]

        ax.plot(range(proj_start, proj_start + len(proj_labels)), proj_medianas,
               'o--', color=self.COLORS['accent_orange'], linewidth=2, markersize=6,
               label='Proyección Greybark')

        # Formateo
        all_labels = dates + proj_labels
        ax.set_xticks(range(len(all_labels)))
        ax.set_xticklabels(all_labels, rotation=45, ha='right')
        ax.set_ylabel('Fed Funds Rate (%)', fontweight='bold')
        ax.set_title(title, fontsize=12, fontweight='bold', color=self.COLORS['primary_blue'])

        # Neutral rate band
        ax.axhspan(2.75, 3.25, alpha=0.2, color=self.COLORS['positive'], label='Neutral Range')

        ax.legend(loc='upper right')
        plt.tight_layout()
        return self._fig_to_base64(fig)

    # =========================================================================
    # FORECAST FAN CHART
    # =========================================================================

    def generate_forecast_fan(self,
                              historical: List[Tuple[str, float]],
                              forecast_path: List[float],
                              ci_95_path: List[List[float]] = None,
                              title: str = "Forecast Fan Chart",
                              ylabel: str = "%",
                              target_line: float = None,
                              target_label: str = None,
                              additional_lines: Dict[str, List[Tuple[int, float]]] = None) -> str:
        """
        Fan chart: historical line + forecast with confidence bands.

        Args:
            historical: List of (label, value) for past data
            forecast_path: List of forecast values (monthly steps)
            ci_95_path: List of [lo, hi] per forecast step (95% CI)
            target_line: Horizontal target (e.g. 2% inflation target)
            additional_lines: Dict of {model_name: [(step_index, value), ...]}
                              for overlaying VAR/Phillips/Taylor forecasts
        """
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder(title)

        fig, ax = plt.subplots(figsize=(self.width + 1, self.height + 0.5))

        # --- Historical ---
        n_hist = len(historical)
        hist_x = list(range(n_hist))
        hist_y = [h[1] for h in historical]
        hist_labels = [h[0] for h in historical]

        ax.plot(hist_x, hist_y, '-', color=self.COLORS['primary_blue'],
                linewidth=2, label='Histórico', zorder=5)

        # --- Forecast ---
        n_fc = len(forecast_path)
        # Connect forecast to last historical point
        fc_x = list(range(n_hist - 1, n_hist - 1 + n_fc + 1))
        fc_y = [hist_y[-1]] + list(forecast_path)

        ax.plot(fc_x, fc_y, '--', color=self.COLORS['accent_orange'],
                linewidth=2, label='ARIMA Forecast', zorder=5)

        # --- CI 95% band ---
        if ci_95_path and len(ci_95_path) == n_fc:
            ci_x = list(range(n_hist, n_hist + n_fc))
            ci_lo = [ci[0] for ci in ci_95_path]
            ci_hi = [ci[1] for ci in ci_95_path]
            ax.fill_between(ci_x, ci_lo, ci_hi, alpha=0.10,
                            color=self.COLORS['accent_orange'], label='IC 95%')
            # Approximate 68% CI as middle 50% of the 95% band
            ci68_lo = [(lo + fc) / 2 for lo, fc in zip(ci_lo, forecast_path)]
            ci68_hi = [(hi + fc) / 2 for hi, fc in zip(ci_hi, forecast_path)]
            ax.fill_between(ci_x, ci68_lo, ci68_hi, alpha=0.25,
                            color=self.COLORS['accent_orange'], label='IC 68%')

        # --- Vertical "Hoy" line ---
        ax.axvline(x=n_hist - 1, color='gray', linestyle=':', linewidth=1, alpha=0.7)
        ax.text(n_hist - 1, ax.get_ylim()[1] * 0.98, ' Hoy', fontsize=7,
                color='gray', va='top')

        # --- Additional model lines (VAR, Phillips, Taylor) ---
        model_colors = {'VAR': '#805ad5', 'Phillips': '#319795', 'Taylor': '#d69e2e'}
        if additional_lines:
            for model_name, points in additional_lines.items():
                if not points:
                    continue
                color = model_colors.get(model_name, '#718096')
                pts_x = [n_hist - 1 + p[0] for p in points]
                pts_y = [p[1] for p in points]
                ax.plot(pts_x, pts_y, 's-', color=color, linewidth=1.5,
                        markersize=5, label=model_name, alpha=0.8, zorder=4)

        # --- Target line ---
        if target_line is not None:
            lbl = target_label or f'Target {target_line}%'
            ax.axhline(y=target_line, color=self.COLORS['positive'],
                        linestyle='--', linewidth=1, alpha=0.6, label=lbl)

        # X-axis labels
        total_n = n_hist + n_fc
        # Generate forecast month labels
        from datetime import date as _date
        now = _date.today()
        fc_labels = []
        abbr = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
        for i in range(1, n_fc + 1):
            m = (now.month + i - 1) % 12 + 1
            y = now.year + (now.month + i - 1) // 12
            fc_labels.append(f"{abbr[m-1]}{str(y)[2:]}")

        all_labels = hist_labels + fc_labels
        step = max(1, total_n // 10)
        ax.set_xticks(range(0, total_n, step))
        ax.set_xticklabels([all_labels[i] for i in range(0, total_n, step)],
                           rotation=45, ha='right', fontsize=7)

        ax.set_ylabel(ylabel, fontweight='bold')
        ax.set_title(title, fontsize=12, fontweight='bold',
                     color=self.COLORS['primary_blue'])
        ax.legend(fontsize=7, framealpha=0.9, loc='upper left')

        plt.tight_layout()
        return self._fig_to_base64(fig)

    # =========================================================================
    # TAYLOR RULE DECOMPOSITION
    # =========================================================================

    def generate_taylor_decomposition(self,
                                       banks: List[Dict[str, Any]],
                                       title: str = "Taylor Rule: Descomposición") -> str:
        """
        Horizontal stacked bar chart for Taylor Rule decomposition.

        Args:
            banks: List of dicts with:
                - name: str (e.g. 'Fed', 'BCCh', 'ECB')
                - r_star: float
                - inflation: float (current π)
                - inflation_gap: float (0.5 × (π - π*))
                - output_gap: float (0.5 × (y - y*))
                - taylor_rate: float (pure Taylor)
                - actual_rate: float (current policy rate)
        """
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder(title)

        fig, ax = plt.subplots(figsize=(self.width + 1, self.height + 0.3))

        names = [b['name'] for b in banks]
        y_pos = np.arange(len(names))

        # Component colors
        comp_colors = {
            'r*': '#9e9e9e',
            'π': self.SERIES_COLORS[0],
            '0.5(π-π*)': self.COLORS['accent_orange'],
            '0.5(y-y*)': self.COLORS['positive'],
        }

        # Stack components
        left = np.zeros(len(banks))
        components = ['r*', 'π', '0.5(π-π*)', '0.5(y-y*)']
        keys = ['r_star', 'inflation', 'inflation_gap', 'output_gap']

        for comp, key in zip(components, keys):
            values = np.array([b.get(key, 0) for b in banks])
            color = comp_colors[comp]
            bars = ax.barh(y_pos, values, left=left, height=0.5,
                          color=color, label=comp, edgecolor='white', linewidth=0.5)
            # Labels inside bars if |val| > 0.3
            for i, (v, l) in enumerate(zip(values, left)):
                if abs(v) > 0.3:
                    ax.text(l + v / 2, y_pos[i], f'{v:.1f}',
                            ha='center', va='center', fontsize=7,
                            fontweight='bold', color='white')
            left += values

        # Markers: diamond = actual, square = Taylor pure
        for i, b in enumerate(banks):
            ax.plot(b['actual_rate'], y_pos[i], 'D', color=self.COLORS['negative'],
                    markersize=9, zorder=10, markeredgecolor='white', markeredgewidth=1)
            ax.plot(b['taylor_rate'], y_pos[i], 's', color=self.COLORS['accent_orange'],
                    markersize=9, zorder=10, markeredgecolor='white', markeredgewidth=1)

        # Legend entries for markers
        ax.plot([], [], 'D', color=self.COLORS['negative'], markersize=8, label='Tasa Actual')
        ax.plot([], [], 's', color=self.COLORS['accent_orange'], markersize=8, label='Taylor Puro')

        ax.set_yticks(y_pos)
        ax.set_yticklabels(names, fontweight='bold')
        ax.set_xlabel('Tasa (%)', fontweight='bold')
        ax.set_title(title, fontsize=12, fontweight='bold',
                     color=self.COLORS['primary_blue'])
        ax.legend(fontsize=7, loc='lower right', ncol=3, framealpha=0.9)
        ax.axvline(x=0, color='black', linewidth=0.5)

        plt.tight_layout()
        return self._fig_to_base64(fig)

    # =========================================================================
    # SCENARIOS PROBABILITY PIE
    # =========================================================================

    def generate_scenarios_pie(self,
                               scenarios: List[Dict[str, Any]],
                               title: str = "Probabilidad de Escenarios") -> str:
        """
        Genera pie chart de probabilidades de escenarios.
        """
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder(title)

        fig, ax = plt.subplots(figsize=(6, 4))

        labels = [s['nombre'] for s in scenarios]
        sizes = [int(s['probabilidad'].replace('%', '')) for s in scenarios]
        colors = [self.COLORS['positive'], self.COLORS['secondary_blue'], self.COLORS['negative']]
        explode = (0.05, 0, 0.05)

        wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors[:len(sizes)],
                                          autopct='%1.0f%%', startangle=90, explode=explode,
                                          textprops={'fontsize': 10, 'fontweight': 'bold'})

        ax.set_title(title, fontsize=12, fontweight='bold', color=self.COLORS['primary_blue'])

        plt.tight_layout()
        return self._fig_to_base64(fig)

    # =========================================================================
    # COMMODITIES CHART
    # =========================================================================

    def generate_commodities_chart(self,
                                   commodities: List[Dict[str, Any]],
                                   title: str = "Commodities Performance") -> str:
        """
        Genera bar chart de performance de commodities.
        """
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder(title)

        fig, ax = plt.subplots(figsize=(self.width, self.height * 0.8))

        names = [c['nombre'] for c in commodities]
        changes = [self._safe_float(c['cambio']) for c in commodities]

        colors = [self.COLORS['positive'] if c >= 0 else self.COLORS['negative'] for c in changes]

        bars = ax.bar(names, changes, color=colors)

        ax.set_ylabel('Cambio (%)', fontweight='bold')
        ax.set_title(title, fontsize=12, fontweight='bold', color=self.COLORS['primary_blue'])
        ax.axhline(y=0, color='black', linewidth=0.8)

        for bar, change in zip(bars, changes):
            height = bar.get_height()
            ax.annotate(f'{change:+.1f}%',
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3 if height >= 0 else -12),
                       textcoords="offset points",
                       ha='center', fontsize=10, fontweight='bold')

        plt.tight_layout()
        return self._fig_to_base64(fig)

    # =========================================================================
    # TIME SERIES
    # =========================================================================

    def generate_time_series(self,
                             series: Dict[str, List[Tuple[str, float]]],
                             title: str = "Time Series",
                             ylabel: str = "",
                             target_line: float = None,
                             target_label: str = None,
                             dual_axis: Dict[str, List[Tuple[str, float]]] = None,
                             dual_ylabel: str = "") -> str:
        """
        Genera chart de series de tiempo con multiples lineas.

        Args:
            series: Dict label -> [(date_str, value), ...]
            title: Titulo del chart
            ylabel: Label eje Y izquierdo
            target_line: Linea horizontal de referencia
            target_label: Label para la linea de referencia
            dual_axis: Series para eje Y derecho (opcional)
            dual_ylabel: Label eje Y derecho
        """
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder(title)

        fig, ax = plt.subplots(figsize=(self.width, self.height + 0.5))

        for i, (label, data) in enumerate(series.items()):
            dates = [d[0] for d in data]
            values = [d[1] for d in data]
            color = self.SERIES_COLORS[i % len(self.SERIES_COLORS)]
            legend_lbl = self._legend_label(label, values)
            ax.plot(range(len(dates)), values, '-', color=color,
                    linewidth=2, label=legend_lbl, marker='o', markersize=3)

        # Target line
        if target_line is not None:
            ax.axhline(y=target_line, color=self.COLORS['accent_orange'],
                       linestyle='--', linewidth=1.5,
                       label=target_label or f'Target ({target_line})')

        # X-axis: show every Nth label to avoid crowding
        if series:
            first_series = list(series.values())[0]
            dates = [d[0] for d in first_series]
            n = max(1, len(dates) // 8)
            ax.set_xticks(range(0, len(dates), n))
            ax.set_xticklabels([dates[i] for i in range(0, len(dates), n)],
                               rotation=45, ha='right', fontsize=7)

        ax.set_ylabel(ylabel, fontweight='bold')
        ax.set_title(title, fontsize=12, fontweight='bold', color=self.COLORS['primary_blue'])
        ax.legend(loc='best', fontsize=7, framealpha=0.9)

        # Dual axis
        if dual_axis:
            ax2 = ax.twinx()
            for i, (label, data) in enumerate(dual_axis.items()):
                values = [d[1] for d in data]
                color = self.SERIES_COLORS[(i + len(series)) % len(self.SERIES_COLORS)]
                legend_lbl = self._legend_label(label, values)
                ax2.plot(range(len(values)), values, '--', color=color,
                         linewidth=2, label=legend_lbl, marker='s', markersize=3)
            ax2.set_ylabel(dual_ylabel, fontweight='bold')
            ax2.legend(loc='upper left', fontsize=7, framealpha=0.9)

        plt.tight_layout()
        return self._fig_to_base64(fig)

    # =========================================================================
    # STACKED BAR (contribuciónes apiladas)
    # =========================================================================

    def generate_stacked_bar(self,
                              categories: List[str],
                              components: Dict[str, List[float]],
                              title: str = "Stacked Bar",
                              ylabel: str = "",
                              target_line: float = None,
                              target_label: str = None,
                              total_line: bool = True) -> str:
        """
        Genera chart de barras apiladas con componentes positivos y negativos.

        Args:
            categories: Labels del eje X (e.g. fechas)
            components: Dict label -> [valores por categoria].
                        Valores positivos se apilan hacia arriba,
                        negativos hacia abajo.
            title: Titulo del chart
            ylabel: Label eje Y
            target_line: Linea horizontal de referencia
            target_label: Label para la linea de referencia
            total_line: Si True, dibuja linea con el total (suma de componentes)
        """
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder(title)

        fig, ax = plt.subplots(figsize=(self.width, self.height + 0.5))

        x = np.arange(len(categories))
        bar_width = 0.8

        # Separar positivos y negativos para apilar correctamente
        pos_bottom = np.zeros(len(categories))
        neg_bottom = np.zeros(len(categories))

        for i, (label, values) in enumerate(components.items()):
            vals = np.array(values)
            color = self.SERIES_COLORS[i % len(self.SERIES_COLORS)]
            avg = float(np.mean(vals))
            last = float(vals[-1])
            if abs(avg) >= 100:
                legend_lbl = f"{label}  (Prom: {avg:,.0f} | Ult: {last:,.0f})"
            else:
                legend_lbl = f"{label}  (Prom: {avg:.2f} | Ult: {last:.2f})"

            pos_vals = np.where(vals >= 0, vals, 0)
            neg_vals = np.where(vals < 0, vals, 0)

            if np.any(pos_vals > 0):
                ax.bar(x, pos_vals, bar_width, bottom=pos_bottom,
                       color=color, label=legend_lbl, alpha=0.85)
            if np.any(neg_vals < 0):
                ax.bar(x, neg_vals, bar_width, bottom=neg_bottom,
                       color=color, label=legend_lbl if not np.any(pos_vals > 0) else None,
                       alpha=0.85)

            pos_bottom += pos_vals
            neg_bottom += neg_vals

        # Total line
        if total_line:
            totals = np.zeros(len(categories))
            for vals in components.values():
                totals += np.array(vals)
            ax.plot(x, totals, 'k-', linewidth=2, marker='o', markersize=3,
                    label=self._legend_label('CPI Total', list(totals)),
                    zorder=5)

        # Target line
        if target_line is not None:
            ax.axhline(y=target_line, color=self.COLORS['accent_orange'],
                       linestyle='--', linewidth=1.5,
                       label=target_label or f'Target ({target_line})')

        ax.axhline(y=0, color='#999999', linewidth=0.5)

        # X-axis labels
        n = max(1, len(categories) // 10)
        ax.set_xticks(x[::n])
        ax.set_xticklabels([categories[i] for i in range(0, len(categories), n)],
                           rotation=45, ha='right', fontsize=7)

        ax.set_ylabel(ylabel, fontweight='bold')
        ax.set_title(title, fontsize=12, fontweight='bold',
                     color=self.COLORS['primary_blue'])
        ax.legend(loc='best', fontsize=7, framealpha=0.9)

        plt.tight_layout()
        return self._fig_to_base64(fig)

    # =========================================================================
    # MULTI-PANEL (2x2 grid)
    # =========================================================================

    def generate_multi_panel(self,
                             panels: List[Dict[str, Any]],
                             suptitle: str = "") -> str:
        """
        Genera grid 2x2 de mini-charts.

        Args:
            panels: Lista de hasta 4 dicts, cada uno con:
                - 'title': titulo del panel
                - 'series': Dict[str, List[Tuple[str, float]]]
                - 'ylabel': label eje Y
                - 'target_line': opcional
            suptitle: Titulo general de la figura
        """
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder(suptitle or "Multi Panel")

        n = len(panels)
        rows = 2 if n > 2 else 1
        cols = 2 if n > 1 else 1
        fig, axes = plt.subplots(rows, cols, figsize=(self.width + 2, (self.height + 0.5) * rows))

        if n == 1:
            axes = np.array([axes])
        axes_flat = axes.flatten() if hasattr(axes, 'flatten') else [axes]

        for idx, panel in enumerate(panels):
            ax = axes_flat[idx]
            for i, (label, data) in enumerate(panel['series'].items()):
                dates = [d[0] for d in data]
                values = [d[1] for d in data]
                color = self.SERIES_COLORS[i % len(self.SERIES_COLORS)]
                legend_lbl = self._legend_label(label, values)
                ax.plot(range(len(dates)), values, '-', color=color,
                        linewidth=1.5, label=legend_lbl, marker='o', markersize=2)

            if panel.get('target_line') is not None:
                ax.axhline(y=panel['target_line'], color=self.COLORS['accent_orange'],
                           linestyle='--', linewidth=1, alpha=0.7)

            # X labels
            n_dates = len(list(panel['series'].values())[0])
            step = max(1, n_dates // 4)
            first_dates = [d[0] for d in list(panel['series'].values())[0]]
            ax.set_xticks(range(0, n_dates, step))
            ax.set_xticklabels([first_dates[i] for i in range(0, n_dates, step)],
                               rotation=45, ha='right', fontsize=6)
            ax.set_title(panel['title'], fontsize=9, fontweight='bold',
                         color=self.COLORS['primary_blue'])
            ax.set_ylabel(panel.get('ylabel', ''), fontsize=7)
            ax.legend(fontsize=6, framealpha=0.9)

        # Hide unused panels
        for idx in range(len(panels), len(axes_flat)):
            axes_flat[idx].set_visible(False)

        if suptitle:
            fig.suptitle(suptitle, fontsize=13, fontweight='bold',
                         color=self.COLORS['primary_blue'], y=1.02)

        plt.tight_layout()
        return self._fig_to_base64(fig)

    # =========================================================================
    # HEATMAP (generic)
    # =========================================================================

    def generate_heatmap(self,
                         row_labels: List[str],
                         col_labels: List[str],
                         data: List[List[float]],
                         title: str = "Heatmap",
                         cmap_thresholds: List[Tuple[float, str]] = None,
                         fmt: str = '.1f',
                         ylabel: str = "") -> str:
        """
        Genera heatmap con valores anotados.

        Args:
            row_labels: labels de filas
            col_labels: labels de columnas
            data: matriz [rows][cols] de valores
            title: titulo
            cmap_thresholds: lista de (threshold, color) para colormap discreto
            fmt: formato de los valores en celdas
        """
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder(title)

        n_rows = len(row_labels)
        n_cols = len(col_labels)
        fig_h = max(3.5, 0.4 * n_rows + 1.5)
        fig_w = max(8, 0.5 * n_cols + 2)
        fig, ax = plt.subplots(figsize=(fig_w, fig_h))

        arr = np.array(data)

        # Colormap: custom discreto basado en thresholds
        if cmap_thresholds:
            from matplotlib.colors import BoundaryNorm, ListedColormap
            bounds = [t[0] for t in cmap_thresholds] + [100]
            colors_list = [t[1] for t in cmap_thresholds]
            cmap = ListedColormap(colors_list)
            norm = BoundaryNorm(bounds, cmap.N)
            im = ax.imshow(arr, cmap=cmap, norm=norm, aspect='auto')
        else:
            im = ax.imshow(arr, cmap='RdYlGn_r', aspect='auto')

        # Ejes
        ax.set_xticks(range(n_cols))
        ax.set_xticklabels(col_labels, rotation=45, ha='right', fontsize=7)
        ax.set_yticks(range(n_rows))
        ax.set_yticklabels(row_labels, fontsize=8)

        # Anotar valores en cada celda
        for i in range(n_rows):
            for j in range(n_cols):
                val = arr[i, j]
                color = 'white' if val > 5 else 'black'
                ax.text(j, i, f'{val:{fmt}}', ha='center', va='center',
                        fontsize=6, fontweight='bold', color=color)

        ax.set_title(title, fontsize=12, fontweight='bold',
                     color=self.COLORS['primary_blue'], pad=10)

        # Colorbar
        cbar = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
        cbar.ax.tick_params(labelsize=7)

        plt.tight_layout()
        return self._fig_to_base64(fig)

    # =========================================================================
    # RISK HEATMAP
    # =========================================================================

    def generate_risk_matrix(self,
                             risks: List[Dict[str, Any]],
                             title: str = "Risk Assessment Matrix") -> str:
        """
        Genera matriz de riesgos (probabilidad vs impacto).
        """
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder(title)

        fig, ax = plt.subplots(figsize=(self.width, self.height))

        # Mapeo de probabilidad/impacto a numeros
        prob_map = {'Baja': 1, 'Media': 2, 'Alta': 3}
        impact_map = {'Bajo': 1, 'Medio': 2, 'Alto': 3, 'Medio-Alto': 2.5}

        for i, risk in enumerate(risks):
            prob_str = risk.get('probabilidad', '25%').replace('%', '')
            try:
                prob = float(prob_str) / 33  # Normalizar a 1-3
            except (ValueError, TypeError):
                prob = prob_map.get(risk.get('probabilidad', 'Media'), 2)

            impact = impact_map.get(risk.get('impacto', 'Medio'), 2)

            size = 500 + prob * 100
            color = self.COLORS['negative'] if prob * impact > 4 else self.COLORS['neutral']

            ax.scatter(prob, impact, s=size, c=color, alpha=0.6, edgecolors='black', linewidth=2)
            ax.annotate(risk['nombre'][:20], (prob, impact),
                       textcoords="offset points", xytext=(10, 5),
                       fontsize=8, fontweight='bold')

        ax.set_xlabel('Probabilidad', fontweight='bold')
        ax.set_ylabel('Impacto', fontweight='bold')
        ax.set_title(title, fontsize=12, fontweight='bold', color=self.COLORS['primary_blue'])
        ax.set_xlim(0.5, 3.5)
        ax.set_ylim(0.5, 3.5)
        ax.set_xticks([1, 2, 3])
        ax.set_xticklabels(['Baja', 'Media', 'Alta'])
        ax.set_yticks([1, 2, 3])
        ax.set_yticklabels(['Bajo', 'Medio', 'Alto'])

        # Background grid for quadrants
        ax.axhline(y=2, color='gray', linestyle='--', alpha=0.3)
        ax.axvline(x=2, color='gray', linestyle='--', alpha=0.3)

        plt.tight_layout()
        return self._fig_to_base64(fig)


# =============================================================================
# MACRO CHARTS GENERATOR
# =============================================================================

class MacroChartsGenerator:
    """Generador de charts especificos para el Reporte Macro."""

    def __init__(self, data_provider=None, forecast_data: Dict = None,
                 branding: Dict = None, bloomberg=None):
        self.chart_gen = ChartGenerator()
        self.data = data_provider  # ChartDataProvider or None (fallback to _interp)
        self.forecast_data = forecast_data or {}
        self.branding = branding or {}
        self.bloomberg = bloomberg  # BloombergData instance for PMI, CPI components, China trade
        self.chart_sources: Dict[str, str] = {}  # chart_id → 'real_api' | 'bloomberg' | 'fallback'

    def get_chart_source_summary(self) -> Dict[str, Any]:
        """Return summary of data sources used across all charts."""
        real = [k for k, v in self.chart_sources.items() if v == 'real_api']
        bbg = [k for k, v in self.chart_sources.items() if v == 'bloomberg']
        fallback = [k for k, v in self.chart_sources.items() if v == 'fallback']
        content = [k for k, v in self.chart_sources.items() if v == 'content']
        total = len(self.chart_sources) or 1
        real_count = len(real) + len(bbg)
        return {
            'real_api': len(real),
            'bloomberg': len(bbg),
            'partial_real': 0,
            'fallback_estimated': len(fallback),
            'content_generated': len(content),
            'real_pct': round(real_count / total * 100),
            'details': {
                'real': real,
                'bloomberg': bbg,
                'fallback': fallback,
                'content': content,
            },
        }

    def _sync_spot(self, series: list, spot_key: str) -> list:
        """Override last data point with injected spot value for chart/text consistency.

        If the ChartDataProvider has an injected spot value for `spot_key`,
        replace the last (date, value) tuple so the chart legend "Ult:" matches
        the value used in report text.
        """
        if not self.data or not series:
            return series
        spot = self.data.get_spot(spot_key)
        if spot is not None:
            series = list(series)  # copy
            date_last = series[-1][0]
            series[-1] = (date_last, spot)
        return series

    def generate_all_charts(self, content: Dict[str, Any]) -> Dict[str, str]:
        """
        Genera todos los charts para el reporte macro.

        Args:
            content: Contenido del reporte (de MacroContentGenerator)

        Returns:
            Dict con chart_id -> base64 image o HTML
        """
        charts = {}

        def _safe_chart(chart_id, fn):
            """Generate a chart with error isolation."""
            try:
                result = fn()
                if result:
                    charts[chart_id] = result
            except ChartDataError as e:
                logger.error("Chart '%s' BLOCKED — no data: %s", chart_id, e)
            except Exception as e:
                print(f"  [WARN] Chart '{chart_id}' failed: {e}")

        # 0. Time Series Charts (new)
        try:
            ts_charts = self.generate_macro_time_series_charts()
            charts.update(ts_charts)
        except Exception as e:
            print(f"  [WARN] Time series charts failed: {e}")

        # 1. Yield Curve + Spreads (now in generate_macro_time_series_charts)

        # 2. GDP Comparison
        if 'resumen_ejecutivo' in content:
            forecasts = content['resumen_ejecutivo'].get('forecasts_table', {})
            gdp_data = forecasts.get('gdp_growth', [])
            if gdp_data:
                chart_data = []
                for row in gdp_data[:5]:
                    chart_data.append({
                        'region': row['region'],
                        'actual': row['actual_2025'],
                        'forecast': row['forecast_2026'],
                        'consenso': row['consenso']
                    })
                _safe_chart('gdp_comparison',
                            lambda: self.chart_gen.generate_gdp_comparison(chart_data))

        # 3. Inflation Decomposition
        if 'estados_unidos' in content:
            inflation = content['estados_unidos'].get('inflación', {})
            components = inflation.get('componentes', [])
            if components:
                chart_components = [{'nombre': c['componente'], 'valor': c['valor']} for c in components]
                _safe_chart('inflation_decomposition',
                            lambda: self.chart_gen.generate_inflation_decomposition(chart_components))

        # 4. Scenarios Pie
        if 'pronóstico_ponderado' in content:
            escenarios = content['pronóstico_ponderado'].get('escenarios', [])
            if escenarios:
                _safe_chart('scenarios_pie',
                            lambda: self.chart_gen.generate_scenarios_pie(escenarios))

        # 5. Commodities
        if 'chile_latam' in content:
            commodities = content['chile_latam'].get('commodities_relevantes', {}).get('commodities', [])
            if commodities:
                _safe_chart('commodities',
                            lambda: self.chart_gen.generate_commodities_chart(commodities))

        # 6. Risk Matrix
        if 'escenarios_riesgos' in content:
            risks = content['escenarios_riesgos'].get('top_risks', [])
            if risks:
                _safe_chart('risk_matrix',
                            lambda: self.chart_gen.generate_risk_matrix(risks))

        return charts

    # =========================================================================
    # HELPERS: monthly labels + milestone interpolation
    # =========================================================================

    def _monthly_labels(self, n=120, start_year=2016, start_month=2) -> List[str]:
        """Genera labels mensuales: 'Feb16','Mar16',...,'Jan26'."""
        abbr = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
        labels = []
        y, m = start_year, start_month
        for _ in range(n):
            labels.append(f"{abbr[m-1]}{str(y)[2:]}")
            m += 1
            if m > 12:
                m = 1
                y += 1
        return labels

    def _interp(self, milestones: Dict[int, float], n: int = 120,
                noise: float = 0.0, seed: int = 42) -> List[float]:
        """
        Interpola linealmente entre milestones y agrega ruido opcional.

        Args:
            milestones: {month_index: value} — index 0=Feb16, 119=Jan26
            n: total data points
            noise: std dev del ruido gaussiano
            seed: seed para reproducibilidad
        """
        índices = sorted(milestones.keys())
        values = [milestones[i] for i in índices]
        result = list(np.interp(range(n), índices, values))
        if noise > 0:
            rng = np.random.RandomState(seed)
            result = [v + rng.normal(0, noise) for v in result]
        return [round(v, 2) for v in result]

    def _real_series(self, series: 'pd.Series', date_fmt: str = '%b%y') -> Optional[List[Tuple[str, float]]]:
        """
        Convierte pd.Series real a chart data format.
        Returns None if series is None or empty.
        """
        if series is None or (hasattr(series, '__len__') and len(series) == 0):
            return None
        try:
            import pandas as pd
            result = []
            for dt, val in series.items():
                try:
                    label = pd.Timestamp(dt).strftime(date_fmt)
                    result.append((label, round(float(val), 2)))
                except (ValueError, TypeError):
                    continue
            return result if len(result) > 10 else None
        except Exception:
            return None

    # =========================================================================
    # TIME SERIES CHARTS (120 months: Feb 2016 — Jan 2026)
    # =========================================================================
    #
    # Month index reference:
    #   0=Feb16  10=Dec16  22=Dec17  34=Dec18  46=Dec19
    #  49=Mar20(COVID)  50=Apr20  58=Dec20  70=Dec21
    #  76=Jun22  82=Dec22  94=Dec23  106=Dec24  119=Jan26

    def generate_macro_time_series_charts(self) -> Dict[str, str]:
        """Genera los charts de series de tiempo para el reporte macro."""
        charts = {}
        self._chart_failures = []

        chart_methods = {
            'inflation_evolution': self._generate_inflation_evolution,
            'labor_unemployment': self._generate_labor_unemployment,
            'labor_nfp': self._generate_labor_nfp,
            'labor_jolts': self._generate_labor_jolts,
            'labor_wages': self._generate_labor_wages,
            'inflation_heatmap': self._generate_inflation_heatmap,
            'inflation_components_ts': self._generate_inflation_components_ts,
            'pmi_global': self._generate_pmi_global,
            'commodity_prices': self._generate_commodity_prices,
            'energy_food': self._generate_energy_food,
            'fed_vs_ecb_bcch': self._generate_policy_rates_comparison,
            'usa_leading_indicators': self._generate_usa_leading_indicators,
            'europe_dashboard': self._generate_europe_dashboard,
            'europe_pmi': self._generate_europe_pmi,
            'global_equities': self._generate_global_equities,
            'china_dashboard': self._generate_china_dashboard,
            'china_trade': self._generate_china_trade_chart,
            'chile_dashboard': self._generate_chile_dashboard,
            'chile_inflation_components': self._generate_chile_inflation_components,
            'chile_external': self._generate_chile_external_chart,
            'latam_rates': self._generate_latam_rates,
            'epu_geopolitics': self._generate_epu_geopolitics,
            'yield_curve': self._generate_yield_curve,
            'yield_spreads': self._generate_yield_spreads,
        }
        for chart_id, method in chart_methods.items():
            try:
                result = method()
                if result:
                    charts[chart_id] = result
            except ChartDataError as e:
                self._chart_failures.append({'chart_id': chart_id, 'error': str(e)})
                logger.error("Chart '%s' BLOCKED — no data: %s", chart_id, e)
            except Exception as e:
                self._chart_failures.append({'chart_id': chart_id, 'error': str(e)})
                logger.warning("Chart '%s' failed: %s", chart_id, e)
        return charts

    def get_chart_failures(self) -> List[Dict]:
        """Return list of charts that failed due to missing data."""
        return getattr(self, '_chart_failures', [])

    def _generate_inflation_evolution(self) -> str:
        """Inflación Core: Principales Economías (120m, Feb 2016 - Jan 2026)."""
        if not self.data:
            raise ChartDataError("inflation_evolution: ChartDataProvider not available")

        intl = self.data.get_inflation_intl()
        chile_ipc = self.data.get_chile_ipc_yoy()
        usa_real = self._real_series(intl.get('USA'))
        euro_real = self._real_series(intl.get('Eurozona'))
        chile_real = self._real_series(chile_ipc)
        if not (usa_real and euro_real and chile_real):
            raise ChartDataError("inflation_evolution: API returned no data")

        series = {
            'USA CPI YoY': usa_real,
            'Euro CPI YoY': euro_real,
            'Chile IPC YoY': chile_real,
        }
        return self.chart_gen.generate_time_series(
            series, title='Inflación: Principales Economías (datos reales BCCh)',
            ylabel='% a/a', target_line=2.0, target_label='Target 2%')

    def _generate_labor_unemployment(self) -> str:
        """Desempleo USA: U3 + U6 (120m)."""
        if not self.data:
            raise ChartDataError("labor_unemployment: ChartDataProvider not available")

        unemp = self.data.get_usa_unemployment()
        u3_real = self._real_series(unemp.get('u3'))
        u6_real = self._real_series(unemp.get('u6'))
        if not (u3_real and u6_real):
            raise ChartDataError("labor_unemployment: API returned no data")

        series = {
            'U3 (Oficial)': u3_real,
            'U6 (Amplio)': u6_real,
        }
        return self.chart_gen.generate_time_series(
            series, title='Tasa de Desempleo USA: U3 vs U6 (datos FRED)',
            ylabel='%', target_line=4.0, target_label='NAIRU ~4.0%')

    def _generate_labor_nfp(self) -> str:
        """Non-Farm Payrolls mensual (120m). Trunca extremos COVID y los anota."""
        if not MATPLOTLIB_AVAILABLE:
            return self.chart_gen._create_placeholder('Non-Farm Payrolls')

        if not self.data:
            raise ChartDataError("labor_nfp: ChartDataProvider not available")

        nfp_series = self.data.get_usa_nfp()
        if nfp_series is None or len(nfp_series) <= 24:
            raise ChartDataError("labor_nfp: API returned no data")

        import pandas as _pd
        months = [_pd.Timestamp(dt).strftime('%b%y') for dt in nfp_series.index]
        nfp_raw = [float(v) for v in nfp_series.values]

        # Identificar outliers y truncar para legibilidad
        CLIP_MIN = -1500
        CLIP_MAX = 1500
        nfp_clipped = []
        outliers = []  # (index, raw_value)
        for i, v in enumerate(nfp_raw):
            if v < CLIP_MIN:
                outliers.append((i, v))
                nfp_clipped.append(CLIP_MIN)
            elif v > CLIP_MAX:
                outliers.append((i, v))
                nfp_clipped.append(CLIP_MAX)
            else:
                nfp_clipped.append(v)

        gen = self.chart_gen
        fig, ax = plt.subplots(figsize=(gen.width, gen.height + 0.5))

        # Barras coloreadas: positivo=verde, negativo=rojo
        colors = [gen.COLORS['positive'] if v >= 0 else gen.COLORS['negative']
                  for v in nfp_clipped]
        ax.bar(range(len(months)), nfp_clipped, color=colors, width=1.0, alpha=0.7)

        # Linea cero
        ax.axhline(y=0, color='black', linewidth=0.8)

        # Anotar solo el outlier mas extremo
        if outliers:
            worst = min(outliers, key=lambda x: x[1]) if any(v < 0 for _, v in outliers) else max(outliers, key=lambda x: abs(x[1]))
            idx, raw_val = worst
            label = f"{months[idx]}: {raw_val/1000:+,.1f}M" if abs(raw_val) >= 1000 else f"{months[idx]}: {raw_val:+,.0f}K"
            y_pos = CLIP_MIN if raw_val < 0 else CLIP_MAX
            ax.annotate(label,
                        xy=(idx, y_pos), xytext=(idx + 10, y_pos * 0.6),
                        fontsize=8, fontweight='bold', color=gen.COLORS['negative'] if raw_val < 0 else gen.COLORS['positive'],
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                                  edgecolor=gen.COLORS['negative'] if raw_val < 0 else gen.COLORS['positive'], alpha=0.9),
                        arrowprops=dict(arrowstyle='->', color='black', lw=1))

        # Zona truncada con hatching
        if any(v < CLIP_MIN for v in nfp_raw):
            ax.axhspan(CLIP_MIN - 200, CLIP_MIN, color='white', alpha=0.9)
            ax.plot([0, len(months)-1], [CLIP_MIN, CLIP_MIN], '--', color='gray', linewidth=0.8, alpha=0.5)

        # X-axis labels
        n = max(1, len(months) // 8)
        ax.set_xticks(range(0, len(months), n))
        ax.set_xticklabels([months[i] for i in range(0, len(months), n)],
                           rotation=45, ha='right', fontsize=7)

        ax.set_ylabel('Miles de empleos', fontweight='bold')
        nfp_title = 'Non-Farm Payrolls Mensual (datos FRED)'
        ax.set_title(nfp_title, fontsize=12,
                      fontweight='bold', color=gen.COLORS['primary_blue'])
        ax.set_ylim(CLIP_MIN - 200, CLIP_MAX + 200)

        plt.tight_layout()
        return gen._fig_to_base64(fig)

    def _generate_labor_jolts(self) -> str:
        """JOLTS: Job Openings, Quits Rate, Ratio Openings/Unemployed (120m)."""
        if not self.data:
            raise ChartDataError("labor_jolts: ChartDataProvider not available")

        jolts = self.data.get_usa_jolts()
        op_real = self._real_series(jolts.get('openings'))
        qt_real = self._real_series(jolts.get('quits'))
        rt_real = self._real_series(jolts.get('ratio'))
        if not (op_real and qt_real):
            raise ChartDataError("labor_jolts: API returned no data")

        # Convert openings from thousands to millions for display
        op_real = [(lbl, round(v / 1000, 2)) for lbl, v in op_real]
        panels = [
            {'title': 'Job Openings (millones)', 'series': {'Openings': op_real},
             'ylabel': 'Millones'},
            {'title': 'Quits Rate (%)', 'series': {'Quits': qt_real},
             'ylabel': '%'},
        ]
        if rt_real:
            panels.append({'title': 'Ratio Openings / Desempleados',
                           'series': {'Ratio': rt_real},
                           'ylabel': 'Ratio', 'target_line': 1.0})
        return self.chart_gen.generate_multi_panel(
            panels, suptitle='JOLTS — Dinámica del Mercado Laboral USA (datos FRED)')

    def _generate_labor_wages(self) -> str:
        """Salarios y Participación Laboral (120m)."""
        if not self.data:
            raise ChartDataError("labor_wages: ChartDataProvider not available")

        wages = self.data.get_usa_wages()
        ahe_r = self._real_series(wages.get('ahe_yoy'))
        lfpr_r = self._real_series(wages.get('lfpr'))
        prime_r = self._real_series(wages.get('prime_age'))
        eci_r = self._real_series(wages.get('eci_yoy'))
        if not (ahe_r and lfpr_r and prime_r):
            raise ChartDataError("labor_wages: API returned no data")

        panels = [
            {'title': 'AHE (% a/a)', 'series': {'AHE': ahe_r},
             'ylabel': '% a/a', 'target_line': 3.5},
        ]
        if eci_r:
            panels.append({'title': 'ECI (% a/a)', 'series': {'ECI': eci_r},
                           'ylabel': '% a/a', 'target_line': 3.5})
        panels.extend([
            {'title': 'Participación Laboral (%)', 'series': {'LFPR': lfpr_r},
             'ylabel': '%'},
            {'title': 'Participación Prime-Age 25-54 (%)', 'series': {'Prime-Age': prime_r},
             'ylabel': '%'},
        ])
        return self.chart_gen.generate_multi_panel(
            panels, suptitle='Salarios y Participación Laboral USA (datos FRED)')

    def _generate_inflation_heatmap(self) -> str:
        """Heatmap de inflación CPI headline por pais (24 meses)."""
        if not self.data:
            raise ChartDataError("inflation_heatmap: ChartDataProvider not available")

        heatmap_data = self.data.get_inflation_heatmap_data(months=24)
        if not heatmap_data or len(heatmap_data.get('data', [])) < 5:
            raise ChartDataError("inflation_heatmap: API returned insufficient data")

        return self.chart_gen.generate_heatmap(
            row_labels=heatmap_data['countries'],
            col_labels=heatmap_data['col_labels'],
            data=heatmap_data['data'],
            title='Inflación CPI Headline por País (% a/a, datos reales BCCh)',
            cmap_thresholds=[
                (-2, '#2166ac'),
                (0, '#67a9cf'),
                (2, '#d1e5f0'),
                (3, '#fddbc7'),
                (4, '#ef8a62'),
                (5, '#b2182b'),
            ],
            fmt='.1f')

    def _generate_inflation_components_ts(self) -> str:
        """Contribución de cada componente al CPI total (barras apiladas, 36m)."""
        # Try FRED first (free CPI subcomponent indices)
        if self.data:
            try:
                breakdown = self.data.get_usa_cpi_breakdown()
                weights = {
                    'Shelter': ('shelter', 0.36),
                    'Services ex-Hous.': ('services_ex_shelter', 0.25),
                    'Core Goods': ('core_goods', 0.18),
                    'Food': ('food', 0.14),
                    'Energy': ('energy', 0.07),
                }
                components = {}
                all_ok = True
                for label, (key, weight) in weights.items():
                    s = breakdown.get(key)
                    if s is not None and len(s) >= 12:
                        vals = self._real_series(s, date_fmt='%b%y')
                        if vals:
                            components[label] = [(d, round(v * weight, 2)) for d, v in vals[-36:]]
                        else:
                            all_ok = False
                    else:
                        all_ok = False
                if all_ok and len(components) == 5:
                    categories = [d for d, _ in list(components.values())[0]]
                    comp_dict = {k: [v for _, v in pts] for k, pts in components.items()}
                    self.chart_sources['inflation_components_ts'] = 'fred'
                    return self.chart_gen.generate_stacked_bar(
                        categories=categories,
                        components=comp_dict,
                        title='USA: Contribución al CPI por Componente',
                        ylabel='Contribución (pp)',
                        target_line=2.0,
                        target_label='Target Fed 2%')
            except Exception as e:
                logger.warning("inflation_components_ts FRED fallback failed: %s", e)

        raise ChartDataError("inflation_components_ts: no data source available")

    def _generate_pmi_global(self) -> str:
        """PMI Manufacturing Global (120m). Bloomberg-only (ISM PMI is proprietary)."""
        if not self.bloomberg:
            raise ChartDataError("pmi_global: Bloomberg not available (PMI is proprietary)")

        usa_s = self.bloomberg.get_series('pmi_usa_mfg')
        euro_s = self.bloomberg.get_series('pmi_euro_mfg')
        china_s = self.bloomberg.get_series('pmi_china_mfg')
        usa_r = self._real_series(usa_s)
        euro_r = self._real_series(euro_s)
        china_r = self._real_series(china_s)
        if not (usa_r and euro_r and china_r):
            raise ChartDataError("pmi_global: Bloomberg returned incomplete data")

        series = {
            'USA ISM Mfg': usa_r,
            'Euro PMI Mfg': euro_r,
            'China PMI Mfg': china_r,
        }
        self.chart_sources['pmi_global'] = 'bloomberg'
        return self.chart_gen.generate_time_series(
            series, title='PMI Manufacturing Global (datos Bloomberg)',
            ylabel='Índice', target_line=50.0,
            target_label='Expansión/Contracción')

    def _generate_commodity_prices(self) -> str:
        """Precios Commodities: Brent, Cobre, Oro en USD (120m)."""
        if not self.data:
            raise ChartDataError("commodity_prices: ChartDataProvider not available")

        comm = self.data.get_commodities()
        brent_r = self._real_series(comm.get('brent'))
        cobre_r = self._real_series(comm.get('cobre'))
        oro_r = self._real_series(comm.get('oro'))
        if not (brent_r and cobre_r and oro_r):
            raise ChartDataError("commodity_prices: API returned no data")

        # Sync spot values with text for consistency (Bug 1)
        cobre_r = self._sync_spot(cobre_r, 'copper')
        panels = [
            {'title': 'Brent (USD/bbl)', 'series': {'Brent': brent_r}, 'ylabel': 'USD/bbl'},
            {'title': 'Cobre (USD/lb)', 'series': {'Cobre': cobre_r}, 'ylabel': 'USD/lb'},
            {'title': 'Oro (USD/oz)', 'series': {'Oro': oro_r}, 'ylabel': 'USD/oz'},
        ]
        return self.chart_gen.generate_multi_panel(
            panels, suptitle='Precios Commodities Clave (datos reales BCCh)')

    def _generate_energy_food(self) -> str:
        """Energía y Alimentos: Oil, Gas Natural (120m, USD)."""
        if not self.data:
            raise ChartDataError("energy_food: ChartDataProvider not available")

        energy = self.data.get_energy()
        wti_r = self._real_series(energy.get('wti'))
        gas_r = self._real_series(energy.get('gas'))
        if not (wti_r and gas_r):
            raise ChartDataError("energy_food: API returned no data")

        panels = [
            {'title': 'WTI Crude (USD/bbl)', 'series': {'WTI': wti_r}, 'ylabel': 'USD/bbl'},
            {'title': 'Gas Natural (USD/MMBtu)', 'series': {'Gas Natural': gas_r}, 'ylabel': 'USD/MMBtu'},
        ]
        return self.chart_gen.generate_multi_panel(
            panels, suptitle='Energía y Alimentos (datos BCCh)')

    def _generate_policy_rates_comparison(self) -> str:
        """Tasas de Política: 6 bancos centrales en multi-panel 3x2 (120m)."""
        if not self.data:
            raise ChartDataError("fed_vs_ecb_bcch: ChartDataProvider not available")

        rates = self.data.get_policy_rates()
        real_series = {}
        for name, s in rates.items():
            r = self._real_series(s)
            if r:
                real_series[name] = r
        if len(real_series) < 4:
            raise ChartDataError("fed_vs_ecb_bcch: API returned insufficient data (%d series)" % len(real_series))

        # Sync TPM spot value with text (Bug 1)
        if 'BCCh (Chile)' in real_series:
            real_series['BCCh (Chile)'] = self._sync_spot(real_series['BCCh (Chile)'], 'tpm')
        return self.chart_gen.generate_time_series(
            real_series, title='Tasas de Política Monetaria (datos reales BCCh)',
            ylabel='Tasa (%)')

    def _generate_usa_leading_indicators(self) -> str:
        """USA Leading Indicators: Mfg New Orders, Housing Starts, Consumer Confidence, UMich (120m)."""
        if not self.data:
            raise ChartDataError("usa_leading_indicators: ChartDataProvider not available")

        leading = self.data.get_usa_leading()
        no_r = self._real_series(leading.get('mfg_new_orders_bn'))
        hs_r = self._real_series(leading.get('housing_starts'))
        cc_r = self._real_series(leading.get('consumer_confidence'))
        um_r = self._real_series(leading.get('umich_sentiment'))
        if not (hs_r and (no_r or um_r)):
            raise ChartDataError("usa_leading_indicators: API returned insufficient data")

        # Housing starts: convert thousands to millions
        hs_r = [(lbl, round(v / 1000, 3)) for lbl, v in hs_r]
        panels = []
        if no_r:
            panels.append({'title': 'Mfg New Orders (USD bn)',
                           'series': {'New Orders': no_r}, 'ylabel': 'USD bn'})
        if um_r:
            panels.append({'title': 'UMich Sentiment', 'series': {'UMich': um_r},
                           'ylabel': 'Índice'})
        panels.append({'title': 'Housing Starts (M, SAAR)',
                       'series': {'Housing Starts': hs_r}, 'ylabel': 'Millones'})
        if cc_r:
            panels.append({'title': 'Consumer Confidence',
                           'series': {'OECD CLI': cc_r}, 'ylabel': 'Índice'})
        return self.chart_gen.generate_multi_panel(
            panels, suptitle='USA Leading Indicators (datos FRED)')

    # =========================================================================
    # GLOBAL EQUITIES
    # =========================================================================

    def _generate_global_equities(self) -> str:
        """Bolsas globales: S&P500, DAX, Shanghai, IPSA (120m, datos BCCh)."""
        if not self.data:
            raise ChartDataError("global_equities: ChartDataProvider not available")

        from greybark.config import BCChSeries
        series_map = {
            'S&P 500': BCChSeries.SP500,
            'DAX': BCChSeries.DAX,
            'Shanghai': BCChSeries.SHANGHAI,
            'IPSA': BCChSeries.IPSA,
        }
        real_series = {}
        for name, sid in series_map.items():
            s = self.data.get_series(sid, resample='M')
            r = self._real_series(s)
            if r:
                real_series[name] = r
        if len(real_series) < 3:
            raise ChartDataError("global_equities: API returned insufficient data (%d series)" % len(real_series))

        # Normalize to base 100 at first common date
        normalized = {}
        for name, data in real_series.items():
            base = data[0][1]
            if base and base != 0:
                normalized[name] = [(d, round(v / base * 100, 1)) for d, v in data]
            else:
                normalized[name] = data
        return self.chart_gen.generate_time_series(
            normalized,
            title='Bolsas Globales — Base 100 (datos reales BCCh)',
            ylabel='Índice (base 100)',
            target_line=100.0,
            target_label='Base')

    # =========================================================================
    # EUROPA CHARTS
    # =========================================================================

    def _generate_europe_dashboard(self) -> str:
        """Europe macro dashboard: GDP, CPI, Core CPI, Unemployment (datos BCCh)."""
        if not self.data:
            raise ChartDataError("europe_dashboard: ChartDataProvider not available")

        eu = self.data.get_europe_dashboard()
        gdp_r = self._real_series(eu.get('gdp'))
        cpi_r = self._real_series(eu.get('cpi'))
        core_r = self._real_series(eu.get('core_cpi'))
        desemp_r = self._real_series(eu.get('unemployment'))
        if not (gdp_r and cpi_r and core_r and desemp_r):
            raise ChartDataError("europe_dashboard: API returned incomplete data")

        panels = [
            {'title': 'GDP Eurozona (% t/t)', 'series': {
                'GDP QoQ': gdp_r},
             'ylabel': '% t/t', 'target_line': 0},
            {'title': 'CPI Headline (% a/a)', 'series': {
                'CPI YoY': cpi_r},
             'ylabel': '% a/a', 'target_line': 2.0, 'target_label': 'Meta BCE'},
            {'title': 'CPI Core (% a/a)', 'series': {
                'Core CPI': core_r},
             'ylabel': '% a/a', 'target_line': 2.0},
            {'title': 'Desempleo (%)', 'series': {
                'Desempleo': desemp_r},
             'ylabel': '%'},
        ]
        return self.chart_gen.generate_multi_panel(
            panels, suptitle='Europa: Dashboard Macro (datos BCCh)')

    def _generate_europe_pmi(self) -> str:
        """PMI Europa: Manufacturing, Services, Composite (120m). Bloomberg-only (PMI proprietary)."""
        if not self.bloomberg:
            raise ChartDataError("europe_pmi: Bloomberg not available (PMI is proprietary)")

        mfg_s = self.bloomberg.get_series('pmi_euro_mfg')
        svc_s = self.bloomberg.get_series('pmi_euro_svc')
        comp_s = self.bloomberg.get_series('pmi_euro_comp')
        mfg_r = self._real_series(mfg_s)
        svc_r = self._real_series(svc_s)
        if not (mfg_r and svc_r):
            raise ChartDataError("europe_pmi: Bloomberg returned incomplete data")

        series = {'PMI Manufacturing': mfg_r, 'PMI Services': svc_r}
        if comp_s is not None:
            comp_r = self._real_series(comp_s)
            if comp_r:
                series['PMI Composite'] = comp_r
        self.chart_sources['europe_pmi'] = 'bloomberg'
        return self.chart_gen.generate_time_series(
            series, title='Europa: PMI Eurozona (datos Bloomberg)',
            ylabel='Índice', target_line=50.0,
            target_label='Expansión/Contracción')

    # =========================================================================
    # CHINA CHARTS
    # =========================================================================

    def _generate_china_dashboard(self) -> str:
        """China macro dashboard: GDP, CPI, PPI, Unemployment (120m)."""
        if not self.data:
            raise ChartDataError("china_dashboard: ChartDataProvider not available")

        china = self.data.get_china_dashboard_data()
        gdp_r = self._real_series(china.get('gdp'))
        cpi_r = self._real_series(china.get('cpi'))
        ppi_r = self._real_series(china.get('ppi'))
        desemp_r = self._real_series(china.get('unemployment'))
        if not (gdp_r and cpi_r and ppi_r and desemp_r):
            raise ChartDataError("china_dashboard: API returned incomplete data")

        panels = [
            {'title': 'GDP (% t/t)', 'series': {
                'GDP QoQ': gdp_r},
             'ylabel': '% t/t'},
            {'title': 'CPI (% a/a)', 'series': {
                'CPI YoY': cpi_r},
             'ylabel': '% a/a', 'target_line': 2.0},
            {'title': 'PPI (% a/a)', 'series': {
                'PPI YoY': ppi_r},
             'ylabel': '% a/a', 'target_line': 0},
            {'title': 'Desempleo Urbano (%)', 'series': {
                'Desempleo': desemp_r},
             'ylabel': '%'},
        ]
        return self.chart_gen.generate_multi_panel(
            panels, suptitle='China: Dashboard Macro (datos BCCh)')

    def _generate_china_trade_chart(self) -> str:
        """China comercio exterior: Exports, Imports, Trade Balance (120m). Bloomberg-only."""
        if not self.bloomberg:
            raise ChartDataError("china_trade: Bloomberg not available (trade data proprietary)")

        exp_s = self.bloomberg.get_series('china_exp_yoy')
        imp_s = self.bloomberg.get_series('china_imp_yoy')
        tbal_s = self.bloomberg.get_series('china_trade_bal')
        # Trim to last 120 months for consistency with other charts
        if exp_s is not None and len(exp_s) > 120:
            exp_s = exp_s.iloc[-120:]
        if imp_s is not None and len(imp_s) > 120:
            imp_s = imp_s.iloc[-120:]
        if tbal_s is not None and len(tbal_s) > 120:
            tbal_s = tbal_s.iloc[-120:]
        exp_r = self._real_series(exp_s)
        imp_r = self._real_series(imp_s)
        if not (exp_r and imp_r):
            raise ChartDataError("china_trade: Bloomberg returned incomplete data")

        series = {
            'Exports (% a/a)': exp_r,
            'Imports (% a/a)': imp_r,
        }
        dual = None
        if tbal_s is not None:
            tbal_r = self._real_series(tbal_s)
            if tbal_r:
                dual = {'Trade Balance ($B)': tbal_r}
        self.chart_sources['china_trade'] = 'bloomberg'
        return self.chart_gen.generate_time_series(
            series, title='China: Comercio Exterior (datos Bloomberg)',
            ylabel='% a/a', target_line=0.0,
            target_label='Sin cambio',
            dual_axis=dual,
            dual_ylabel='$B' if dual else None)

    # =========================================================================
    # CHILE & LATAM CHARTS
    # =========================================================================

    def _generate_chile_dashboard(self) -> str:
        """Chile macro dashboard: IMACEC, Desempleo, IPC, USD/CLP (120m)."""
        if not self.data:
            raise ChartDataError("chile_dashboard: ChartDataProvider not available")

        chile = self.data.get_chile_dashboard()
        imacec_r = self._real_series(chile.get('imacec'))
        desemp_r = self._real_series(chile.get('desempleo'))
        ipc_r = self._real_series(chile.get('ipc_yoy'))
        usdclp_r = self._real_series(chile.get('usd_clp'))
        if not (imacec_r and desemp_r and ipc_r and usdclp_r):
            raise ChartDataError("chile_dashboard: API returned incomplete data")

        panels = [
            {'title': 'IMACEC (% a/a)', 'series': {
                'IMACEC': imacec_r},
             'ylabel': '% a/a', 'target_line': 0},
            {'title': 'Tasa de Desempleo (%)', 'series': {
                'Desempleo': desemp_r},
             'ylabel': '%'},
            {'title': 'Inflación IPC (% a/a)', 'series': {
                'IPC YoY': ipc_r},
             'ylabel': '% a/a', 'target_line': 3.0},
            {'title': 'Tipo de Cambio (USD/CLP)', 'series': {
                'USD/CLP': usdclp_r},
             'ylabel': 'CLP'},
        ]
        return self.chart_gen.generate_multi_panel(
            panels, suptitle='Chile: Dashboard Macro (datos reales BCCh)')

    def _generate_chile_inflation_components(self) -> str:
        """Contribución de cada componente al IPC Chile (barras apiladas, 36m)."""
        if not self.data:
            raise ChartDataError("chile_inflation_components: ChartDataProvider not available")

        ipc = self.data.get_chile_ipc_components(months=36)
        if not ipc or not ipc.get('components') or not ipc.get('categories'):
            raise ChartDataError("chile_inflation_components: API returned no data")

        return self.chart_gen.generate_stacked_bar(
            categories=ipc['categories'],
            components=ipc['components'],
            title='Chile: Contribución al IPC por Componente (pp, datos reales BCCh)',
            ylabel='Contribución (pp)',
            target_line=3.0,
            target_label='Meta BCCh 3%'
        )

    def _generate_chile_external_chart(self) -> str:
        """Chile cuentas externas: Balanza Comercial + Cobre (doble eje, 120m)."""
        if not self.data:
            raise ChartDataError("chile_external: ChartDataProvider not available")

        import pandas as pd
        ext = self.data.get_chile_external()
        exp_s = ext.get('exportaciones')
        imp_s = ext.get('importaciones')
        cobre_s = ext.get('cobre')
        cobre_r = self._real_series(cobre_s)
        if exp_s is None or imp_s is None or not cobre_r:
            raise ChartDataError("chile_external: API returned incomplete data")

        # Align and compute trade balance
        exp_a, imp_a = exp_s.align(imp_s, join='inner')
        balance = exp_a - imp_a
        balance_r = self._real_series(balance)
        exports_r = self._real_series(exp_s)
        imports_r = self._real_series(imp_s)
        if not (balance_r and exports_r and imports_r):
            raise ChartDataError("chile_external: computed series too short")

        series = {
            'Exportaciones (MUSD)': exports_r,
            'Importaciones (MUSD)': imports_r,
            'Balanza Comercial (MUSD)': balance_r,
        }
        return self.chart_gen.generate_time_series(
            series,
            title='Chile: Comercio Exterior (datos reales BCCh)',
            ylabel='MUSD',
            target_line=0.0,
            target_label='Equilibrio',
            dual_axis={'Cobre (USD/lb)': cobre_r},
            dual_ylabel='USD/lb')

    def _generate_latam_rates(self) -> str:
        """Tasas de política monetaria LatAm: BCCh, Selic, Banxico, BanRep (120m)."""
        if not self.data:
            raise ChartDataError("latam_rates: ChartDataProvider not available")

        latam = self.data.get_latam_rates()
        real_series = {}
        for name, s in latam.items():
            r = self._real_series(s)
            if r:
                real_series[name] = r
        if len(real_series) < 3:
            raise ChartDataError("latam_rates: API returned insufficient data (%d series)" % len(real_series))

        return self.chart_gen.generate_time_series(
            real_series,
            title='Tasas de Política Monetaria LatAm (datos reales BCCh)',
            ylabel='Tasa (%)')

    def _generate_epu_geopolitics(self) -> str:
        """Índice de Incertidumbre Política Económica (EPU): USA, China, Europa, Global."""
        if not self.data:
            raise ChartDataError("epu_geopolitics: ChartDataProvider not available")

        epu = self.data.get_epu_intl()
        real_series = {}
        for name, s in epu.items():
            r = self._real_series(s)
            if r:
                real_series[name] = r
        if len(real_series) < 2:
            raise ChartDataError("epu_geopolitics: API returned insufficient data (%d series)" % len(real_series))

        return self.chart_gen.generate_time_series(
            real_series,
            title='Índice de Incertidumbre Política (EPU) — datos BCCh/FRED',
            ylabel='EPU Index (base=100)',
            target_line=200.0,
            target_label='Umbral elevado')

    def _generate_multi_panel_6(self, panels: List[Dict[str, Any]],
                                suptitle: str = "") -> str:
        """Genera grid 3x2 de mini-charts para 6 paneles."""
        if not MATPLOTLIB_AVAILABLE:
            return self.chart_gen._create_placeholder(suptitle or "Multi Panel 6")

        fig, axes = plt.subplots(3, 2, figsize=(self.chart_gen.width + 2,
                                                 (self.chart_gen.height - 0.5) * 3))
        axes_flat = axes.flatten()

        for idx, panel in enumerate(panels):
            ax = axes_flat[idx]
            for i, (label, data) in enumerate(panel['series'].items()):
                dates = [d[0] for d in data]
                values = [d[1] for d in data]
                color = self.chart_gen.SERIES_COLORS[i % len(self.chart_gen.SERIES_COLORS)]
                legend_lbl = self.chart_gen._legend_label(label, values)
                ax.plot(range(len(dates)), values, '-', color=color,
                        linewidth=1.5, label=legend_lbl, marker='o', markersize=1)

            if panel.get('target_line') is not None:
                ax.axhline(y=panel['target_line'], color=self.chart_gen.COLORS['accent_orange'],
                           linestyle='--', linewidth=1, alpha=0.7)

            n_dates = len(list(panel['series'].values())[0])
            step = max(1, n_dates // 4)
            first_dates = [d[0] for d in list(panel['series'].values())[0]]
            ax.set_xticks(range(0, n_dates, step))
            ax.set_xticklabels([first_dates[i] for i in range(0, n_dates, step)],
                               rotation=45, ha='right', fontsize=5)
            ax.set_title(panel['title'], fontsize=8, fontweight='bold',
                         color=self.chart_gen.COLORS['primary_blue'])
            ax.set_ylabel(panel.get('ylabel', ''), fontsize=6)
            ax.legend(fontsize=5, framealpha=0.9)

        for idx in range(len(panels), len(axes_flat)):
            axes_flat[idx].set_visible(False)

        if suptitle:
            fig.suptitle(suptitle, fontsize=12, fontweight='bold',
                         color=self.chart_gen.COLORS['primary_blue'], y=1.01)

        plt.tight_layout()
        return self.chart_gen._fig_to_base64(fig)

    def _generate_yield_curve(self) -> str:
        """Genera yield curve con datos reales FRED."""
        if not self.data:
            raise ChartDataError("yield_curve: ChartDataProvider not available")

        hist = self.data.get_yield_curve_historical()
        current = hist.get('current', {})
        previous = hist.get('previous', {})
        year_ago = hist.get('year_ago', {})
        if len(current) < 4:
            raise ChartDataError("yield_curve: API returned insufficient tenors (%d)" % len(current))

        return self.chart_gen.generate_yield_curve(
            current, previous if len(previous) >= 4 else None,
            year_ago if len(year_ago) >= 4 else None)

    def _generate_yield_spreads(self) -> str:
        """Spreads de curva UST: 2y10y y 3m10y (120m). Indicadores de recesión."""
        if not self.data:
            raise ChartDataError("yield_spreads: ChartDataProvider not available")

        import pandas as _pd
        spreads = self.data.get_yield_spreads()
        y2_s = spreads.get('y2')
        y10_s = spreads.get('y10')
        y3m_s = spreads.get('y3m')
        if y2_s is None or y10_s is None:
            raise ChartDataError("yield_spreads: API returned no data")

        # Align and compute spreads
        df = _pd.DataFrame({'y2': y2_s, 'y10': y10_s}).dropna()
        if y3m_s is not None:
            df['y3m'] = y3m_s
        if len(df) <= 24:
            raise ChartDataError("yield_spreads: insufficient data points (%d)" % len(df))

        spread_2y10y = df['y10'] - df['y2']
        s_2y10y = self._real_series(spread_2y10y)
        if not s_2y10y:
            raise ChartDataError("yield_spreads: computed spread series too short")

        series = {'2Y-10Y Spread': s_2y10y}
        if 'y3m' in df.columns:
            spread_3m10y = df['y10'] - df['y3m']
            s_3m10y = self._real_series(spread_3m10y.dropna())
            if s_3m10y:
                series['3M-10Y Spread'] = s_3m10y
        return self.chart_gen.generate_time_series(
            series,
            title='Spreads Curva UST: Indicadores de Recesión (datos FRED)',
            ylabel='Spread (pp)',
            target_line=0.0,
            target_label='Inversion (0 bp)')


# =============================================================================
# TEST
# =============================================================================

def test_charts():
    """Test de generación de charts."""
    gen = ChartGenerator()

    # Test yield curve
    current = {'3M': 4.5, '2Y': 4.2, '5Y': 4.0, '10Y': 4.1, '30Y': 4.3}
    img = gen.generate_yield_curve(current)
    print(f"Yield curve: {'OK' if img.startswith('data:image') else 'PLACEHOLDER'}")

    # Test GDP
    gdp_data = [
        {'region': 'USA', 'actual': '2.4%', 'forecast': '2.2%', 'consenso': '2.0%'},
        {'region': 'Europe', 'actual': '1.2%', 'forecast': '1.4%', 'consenso': '1.2%'},
        {'region': 'China', 'actual': '4.8%', 'forecast': '4.5%', 'consenso': '4.3%'},
    ]
    img = gen.generate_gdp_comparison(gdp_data)
    print(f"GDP comparison: {'OK' if img.startswith('data:image') else 'PLACEHOLDER'}")

    print("\nCharts test completed!")


if __name__ == "__main__":
    test_charts()
