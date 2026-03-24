# -*- coding: utf-8 -*-
"""
Greybark Research - RF Chart Generator
========================================

Genera charts profesionales para el reporte de Renta Fija.
Usa datos reales del RFDataCollector (market_data dict).

Dependencias:
- matplotlib
- numpy
"""

import base64
import io
import sys
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import date, timedelta
import warnings

# Ensure greybark library is importable
_lib_path = str(Path(__file__).resolve().parent)
if _lib_path not in sys.path:
    sys.path.insert(0, _lib_path)

warnings.filterwarnings('ignore')

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import matplotlib.ticker as mticker
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

from chart_config import get_chart_colors, get_failure_tracker

logger = logging.getLogger(__name__)


class RFChartsGenerator:
    """Generador de charts para el reporte de Renta Fija."""

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
        self.DM_COLORS = scheme.dm_colors
        self.EM_COLORS = scheme.em_colors
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
        """Genera los 8 charts del reporte RF."""
        charts = {}
        chart_methods = {
            'rf_yield_curve': self._generate_yield_curve,
            'rf_credit_spreads': self._generate_credit_spreads,
            'rf_breakevens': self._generate_breakevens,
            'rf_chile_curves': self._generate_chile_curves,
            'rf_policy_rates': self._generate_policy_rates,
            'rf_fed_expectations': self._generate_fed_expectations,
            'rf_tpm_expectations': self._generate_tpm_expectations,
            'rf_intl_yields': self._generate_intl_yields,
        }
        for chart_id, method in chart_methods.items():
            try:
                charts[chart_id] = method()
            except Exception as e:
                self._failure_tracker.record(chart_id, str(e), fallback_used=True)
                logger.warning("Chart '%s' failed: %s", chart_id, e)
                charts[chart_id] = self._create_placeholder(chart_id)
        return charts

    # Tenor labels → years (for proportional x-axis)
    TENOR_YEARS = {
        '1M': 1/12, '3M': 0.25, '6M': 0.5, '1Y': 1, '2Y': 2,
        '3Y': 3, '5Y': 5, '7Y': 7, '10Y': 10, '20Y': 20, '30Y': 30,
    }

    # FRED series IDs for each UST tenor
    FRED_TENOR_IDS = {
        '3M': 'DGS3MO', '6M': 'DGS6MO', '1Y': 'DGS1', '2Y': 'DGS2',
        '5Y': 'DGS5', '7Y': 'DGS7', '10Y': 'DGS10', '20Y': 'DGS20', '30Y': 'DGS30',
    }

    def _get_fred(self):
        """Lazy-init FRED client."""
        if not hasattr(self, '_fred'):
            try:
                from greybark.data_sources.fred_client import FREDClient
                self._fred = FREDClient()
            except Exception:
                self._fred = None
        return self._fred

    def _fetch_10y_series(self):
        """Fetch 10Y Treasury time series from FRED (last 10Y)."""
        fred = self._get_fred()
        if not fred:
            return None
        try:
            start = date.today() - timedelta(days=3650)
            series = fred.get_series('DGS10', start_date=start, end_date=date.today())
            if series is not None and len(series) > 10:
                return series.dropna()
        except Exception:
            pass
        return None

    def _fetch_historical_curve(self, target_date):
        """Fetch UST curve at a specific past date from FRED."""
        fred = self._get_fred()
        if not fred:
            return None
        try:
            start = target_date - timedelta(days=10)
            end = target_date + timedelta(days=5)
            curve = {}
            for tenor, sid in self.FRED_TENOR_IDS.items():
                s = fred.get_series(sid, start_date=start, end_date=end)
                if s is not None:
                    s = s.dropna()
                    if len(s) > 0:
                        # Pick closest date <= target
                        before = s[s.index <= str(target_date)]
                        if len(before) > 0:
                            curve[tenor] = float(before.iloc[-1])
                        else:
                            curve[tenor] = float(s.iloc[0])
            return curve if len(curve) >= 5 else None
        except Exception:
            return None

    # =========================================================================
    # 1. UST YIELD CURVE (current vs 1M vs 1Y) + 10Y TIME SERIES (10Y)
    # =========================================================================

    def _generate_yield_curve(self) -> str:
        """Curva UST actual vs 1M vs 1Y (proporcional) + serie 10Y (10 anos)."""
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder('Curva UST')

        curve = self._safe_val(self.data, 'yield_curve', 'current_curve')
        if not curve:
            return self._create_placeholder('Curva UST - sin datos')

        tenor_order = ['3M', '6M', '1Y', '2Y', '5Y', '7Y', '10Y', '20Y', '30Y']
        tenors = [t for t in tenor_order if t in curve]
        yields_now = [curve[t] for t in tenors]
        x_years = [self.TENOR_YEARS[t] for t in tenors]

        if len(tenors) < 3:
            return self._create_placeholder('Curva UST - datos insuficientes')

        # Fetch historical curves + 10Y time series
        today = date.today()
        curve_1m = self._fetch_historical_curve(today - timedelta(days=30))
        curve_1y = self._fetch_historical_curve(today - timedelta(days=365))
        ts_10y = self._fetch_10y_series()
        has_ts = ts_10y is not None and len(ts_10y) > 10

        fig, (ax, ax2) = plt.subplots(1, 2, figsize=(13, 4.5),
                                       gridspec_kw={'width_ratios': [1, 1]})

        # --- Left panel: Yield curves (proportional x-axis) ---

        # Current curve
        ax.plot(x_years, yields_now, color=self.SERIES_COLORS[0], linewidth=2.5,
                marker='o', markersize=5, label='Actual', zorder=4)

        # 1M ago
        if curve_1m:
            y_1m = [curve_1m.get(t) for t in tenors]
            valid_1m = [(x, y) for x, y in zip(x_years, y_1m) if y is not None]
            if valid_1m:
                ax.plot([p[0] for p in valid_1m], [p[1] for p in valid_1m],
                        color=self.COLORS['accent'], linewidth=1.5,
                        marker='o', markersize=3, linestyle='--',
                        label='Hace 1 mes', alpha=0.8, zorder=3)

        # 1Y ago
        if curve_1y:
            y_1y = [curve_1y.get(t) for t in tenors]
            valid_1y = [(x, y) for x, y in zip(x_years, y_1y) if y is not None]
            if valid_1y:
                ax.plot([p[0] for p in valid_1y], [p[1] for p in valid_1y],
                        color=self.COLORS['text_light'], linewidth=1.5,
                        marker='o', markersize=3, linestyle=':',
                        label='Hace 1 ano', alpha=0.7, zorder=2)

        # Annotate current points
        for t, xv, yv in zip(tenors, x_years, yields_now):
            ax.text(xv, yv + 0.06, f'{yv:.2f}', ha='center', va='bottom',
                    fontsize=6.5, fontweight='bold', color=self.SERIES_COLORS[0])

        # Slopes
        slopes = self._safe_val(self.data, 'yield_curve', 'slopes_bps')
        if slopes:
            parts = []
            for label in ['2s10s', '2s30s']:
                val = slopes.get(label)
                if val is not None:
                    parts.append(f'{label}: {val:+.0f}bp')
            if parts:
                ax.text(0.5, -0.12, ' | '.join(parts), transform=ax.transAxes,
                        ha='center', fontsize=8, color=self.COLORS['text_light'],
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))

        # Overlay sovereign curves (Bund, JGB) if available
        sov = self.data.get('sovereign_curves', {}) if self.data else {}
        sov_colors = {'alemania': '#1565C0', 'japon': '#C62828'}
        sov_labels = {'alemania': 'Bund (Alemania)', 'japon': 'JGB (Japón)'}
        sov_yields_all = []
        for country in ('alemania', 'japon'):
            cdata = sov.get(country, {})
            tenor_map = cdata.get('tenors', {})
            if tenor_map and len(tenor_map) >= 3:
                # Map integer tenors to x-axis years
                sov_x = [int(t) for t in sorted(tenor_map.keys(), key=lambda k: int(k))]
                sov_y = [tenor_map[str(t)] for t in sov_x]
                ax.plot(sov_x, sov_y, color=sov_colors[country], linewidth=1.5,
                        marker='s', markersize=3, linestyle='--', alpha=0.7,
                        label=sov_labels[country], zorder=2)
                sov_yields_all.extend(sov_y)

        # Y-axis: tight range (don't start at 0)
        all_yields = yields_now[:]
        if curve_1m:
            all_yields += [v for v in [curve_1m.get(t) for t in tenors] if v is not None]
        if curve_1y:
            all_yields += [v for v in [curve_1y.get(t) for t in tenors] if v is not None]
        all_yields.extend(sov_yields_all)
        y_min = min(all_yields) - 0.25
        y_max = max(all_yields) + 0.35
        ax.set_ylim(y_min, y_max)

        ax.set_xticks(x_years)
        ax.set_xticklabels(tenors, fontsize=8)
        ax.set_xlabel('Plazo', fontsize=9)
        ax.set_ylabel('Yield (%)', fontsize=9)
        ax.set_title('Curvas Soberanas: UST vs Bund vs JGB', fontsize=12, fontweight='bold',
                      color=self.COLORS['primary'], pad=10)
        ax.legend(loc='lower right', fontsize=7)

        # --- Right panel: 10Y time series (10 years) ---
        if has_ts:
            dates = ts_10y.index
            vals = ts_10y.values.astype(float)
            ax2.plot(dates, vals, color=self.SERIES_COLORS[0], linewidth=1.2)
            ax2.fill_between(dates, vals, alpha=0.06, color=self.SERIES_COLORS[0])

            last_val = vals[-1]
            avg_val = np.mean(vals)
            min_val = np.min(vals)
            max_val = np.max(vals)

            ax2.axhline(y=avg_val, color=self.COLORS['accent'], linewidth=1,
                        linestyle='--', alpha=0.7, label=f'Promedio 10A: {avg_val:.2f}%')
            ax2.plot(dates[-1], last_val, 'o', color=self.COLORS['negative'],
                     markersize=6, zorder=5, label=f'Actual: {last_val:.2f}%')

            # Min/max annotations
            ax2.axhline(y=min_val, color=self.COLORS['text_light'], linewidth=0.5,
                        linestyle=':', alpha=0.5)
            ax2.axhline(y=max_val, color=self.COLORS['text_light'], linewidth=0.5,
                        linestyle=':', alpha=0.5)
            ax2.text(dates[0], max_val + 0.05, f'Max: {max_val:.2f}%', fontsize=6.5,
                     color=self.COLORS['text_light'], va='bottom')
            ax2.text(dates[0], min_val - 0.05, f'Min: {min_val:.2f}%', fontsize=6.5,
                     color=self.COLORS['text_light'], va='top')

            ax2.set_ylabel('Yield (%)', fontsize=9)
            ax2.set_title('Treasury 10Y (10 Anos)', fontsize=12, fontweight='bold',
                           color=self.COLORS['primary'], pad=10)
            ax2.legend(loc='upper left', fontsize=7)
            ax2.tick_params(axis='x', rotation=30, labelsize=7)
        else:
            ax2.text(0.5, 0.5, 'Serie 10Y no disponible\n(requiere FRED API)',
                     ha='center', va='center', transform=ax2.transAxes,
                     fontsize=10, color=self.COLORS['text_light'])
            ax2.set_title('Treasury 10Y', fontsize=12, fontweight='bold',
                           color=self.COLORS['primary'], pad=10)

        plt.tight_layout()
        return self._fig_to_base64(fig)

    # =========================================================================
    # 2. CREDIT SPREADS — Range/bullet chart (zone bar + current marker)
    # =========================================================================

    def _generate_credit_spreads(self) -> str:
        """Spreads por rating: rango historico (zonas) con nivel actual marcado."""
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder('Spreads de Credito')

        ig_data = self._safe_val(self.data, 'credit_spreads', 'ig_breakdown')
        hy_data = self._safe_val(self.data, 'credit_spreads', 'hy_breakdown')

        if not ig_data and not hy_data:
            return self._create_placeholder('Spreads de Credito - sin datos')

        # Collect all ratings with thresholds
        entries = []
        rating_keys = [
            ('ig_breakdown', 'aaa', 'AAA (IG)'),
            ('ig_breakdown', 'aa', 'AA (IG)'),
            ('ig_breakdown', 'a', 'A (IG)'),
            ('ig_breakdown', 'bbb', 'BBB (IG)'),
            ('hy_breakdown', 'bb', 'BB (HY)'),
            ('hy_breakdown', 'b', 'B (HY)'),
            ('hy_breakdown', 'ccc', 'CCC (HY)'),
        ]

        for bucket, key, label in rating_keys:
            data_bucket = self._safe_val(self.data, 'credit_spreads', bucket)
            if not data_bucket:
                continue
            entry = data_bucket.get(key)
            if not isinstance(entry, dict) or 'current_bps' not in entry:
                continue
            current = entry['current_bps']
            pct = entry.get('percentile_5y', 0)
            thresholds = entry.get('thresholds', {})
            if not thresholds:
                continue
            entries.append({
                'label': label,
                'current': current,
                'percentile': pct,
                'tight': thresholds.get('tight', 0),
                'normal': thresholds.get('normal', 0),
                'wide': thresholds.get('wide', 0),
                'crisis': thresholds.get('crisis', 0),
                'is_hy': 'HY' in label,
            })

        if not entries:
            return self._create_placeholder('Spreads de Credito - sin datos')

        n = len(entries)
        fig, ax = plt.subplots(figsize=(10, max(3.5, 0.7 * n + 1.5)))

        zone_colors = {
            'tight': '#c6f6d5',   # light green
            'normal': '#fefcbf',  # light yellow
            'wide': '#fed7aa',    # light orange
            'crisis': '#fed7d7',  # light red
        }

        y_positions = np.arange(n)
        bar_h = 0.55

        for i, e in enumerate(entries):
            y = n - 1 - i  # top-to-bottom
            max_x = e['crisis'] * 1.1

            # Draw zone bars (stacked horizontally)
            zones = [
                (0, e['tight'], zone_colors['tight']),
                (e['tight'], e['normal'], zone_colors['normal']),
                (e['normal'], e['wide'], zone_colors['wide']),
                (e['wide'], e['crisis'], zone_colors['crisis']),
            ]
            for x_start, x_end, color in zones:
                ax.barh(y, x_end - x_start, bar_h, left=x_start,
                        color=color, edgecolor='#e2e8f0', linewidth=0.5)

            # Current level marker
            marker_color = self.COLORS['primary']
            ax.plot(e['current'], y, '*', color=marker_color,
                    markersize=14, zorder=5, markeredgecolor='white', markeredgewidth=1)

            # Annotate current + percentile — always past the end of the bar
            text_x = e['crisis'] + max_x * 0.03
            ax.text(text_x, y, f"{e['current']:.0f}bp  ({e['percentile']:.0f}%ile 5A)",
                    va='center', fontsize=7.5, fontweight='bold',
                    color=self.COLORS['text_dark'])

        # Labels
        ax.set_yticks(range(n))
        ax.set_yticklabels([e['label'] for e in reversed(entries)], fontsize=9)
        ax.set_xlabel('Spread (bps)', fontsize=9)
        ax.set_title('Spreads de Credito: Nivel Actual vs Rango Historico',
                      fontsize=12, fontweight='bold',
                      color=self.COLORS['primary'], pad=10)

        # Legend for zones
        from matplotlib.patches import Patch
        legend_items = [
            Patch(facecolor=zone_colors['tight'], edgecolor='#e2e8f0', label='Tight'),
            Patch(facecolor=zone_colors['normal'], edgecolor='#e2e8f0', label='Normal'),
            Patch(facecolor=zone_colors['wide'], edgecolor='#e2e8f0', label='Wide'),
            Patch(facecolor=zone_colors['crisis'], edgecolor='#e2e8f0', label='Crisis'),
            plt.Line2D([0], [0], marker='*', color='w', markerfacecolor=self.COLORS['primary'],
                       markersize=10, label='Actual'),
        ]
        ax.legend(handles=legend_items, loc='lower right', fontsize=7, ncol=5)

        plt.tight_layout()
        return self._fig_to_base64(fig)

    # =========================================================================
    # 3. BREAKEVENS — Inflation Breakevens + Real Rates
    # =========================================================================

    def _generate_breakevens(self) -> str:
        """Breakevens de inflacion y tasas reales (horizontal bars)."""
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder('Breakevens e Inflacion')

        be = self._safe_val(self.data, 'inflation', 'breakeven_inflation', 'current')
        rr = self._safe_val(self.data, 'inflation', 'real_rates', 'current')

        if not be and not rr:
            return self._create_placeholder('Breakevens - sin datos')

        labels = []
        values = []
        colors = []

        # Breakevens
        if be:
            for key, label in [('breakeven_5y', 'Breakeven 5Y'),
                                ('breakeven_10y', 'Breakeven 10Y'),
                                ('forward_5y5y', 'Forward 5Y5Y')]:
                val = be.get(key)
                if val is not None:
                    labels.append(label)
                    values.append(val)
                    colors.append(self.SERIES_COLORS[1])

        # Real rates
        if rr:
            for key, label in [('tips_5y', 'TIPS 5Y (Real)'),
                                ('tips_10y', 'TIPS 10Y (Real)')]:
                val = rr.get(key)
                if val is not None:
                    labels.append(label)
                    values.append(val)
                    colors.append(self.SERIES_COLORS[0])

        if not labels:
            return self._create_placeholder('Breakevens - sin datos')

        fig, ax = plt.subplots(figsize=(8, max(3, 0.6 * len(labels) + 1)))

        y = np.arange(len(labels))
        bars = ax.barh(y, values, color=colors, alpha=0.85, height=0.55)

        for bar, val in zip(bars, values):
            w = bar.get_width()
            ax.text(w + 0.05, bar.get_y() + bar.get_height() / 2,
                    f'{val:.2f}%', va='center', fontsize=9, fontweight='bold',
                    color=self.COLORS['text_dark'])

        # Fed 2% target line
        ax.axvline(x=2.0, color=self.COLORS['negative'], linewidth=1.5,
                   linestyle='--', alpha=0.7, label='Fed Target 2%')

        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=9)
        ax.set_xlabel('Tasa (%)', fontsize=9)
        ax.set_title('Breakevens de Inflacion y Tasas Reales', fontsize=12,
                      fontweight='bold', color=self.COLORS['primary'], pad=10)
        ax.legend(loc='lower right', fontsize=8)
        ax.invert_yaxis()
        plt.tight_layout()
        return self._fig_to_base64(fig)

    # =========================================================================
    # 4. CHILE CURVES — BCP/BTP (right axis) + BCU (left axis), proportional x
    # =========================================================================

    def _generate_chile_curves(self) -> str:
        """Curvas BCP/BTP (nominal, eje derecho) y BCU (real, eje izquierdo).
        BTP 20Y/30Y no existe en BCCh API, se deriva de BCU + breakeven."""
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder('Curvas Chile BCP/BCU')

        bcp = self._safe_val(self.data, 'chile_yields', 'bcp')
        bcu = self._safe_val(self.data, 'chile_yields', 'bcu')

        if not bcp and not bcu:
            return self._create_placeholder('Curvas Chile - sin datos')

        # BCP actual (1Y-10Y)
        bcp_tenors_order = ['1Y', '2Y', '5Y', '10Y']
        bcp_tenors = []
        bcp_yields = []
        if bcp:
            for t in bcp_tenors_order:
                entry = bcp.get(t)
                if isinstance(entry, dict) and 'yield' in entry:
                    bcp_tenors.append(t)
                    bcp_yields.append(entry['yield'])

        # Derive implied BTP 20Y/30Y from BCU + extrapolated breakeven
        breakevens = self._safe_val(self.data, 'chile_yields', 'breakevens') or {}
        be_10y = breakevens.get('10Y')
        implied_btp = {}  # tenor -> yield
        if bcu and be_10y is not None:
            for t in ['20Y', '30Y']:
                bcu_entry = bcu.get(t)
                if isinstance(bcu_entry, dict) and 'yield' in bcu_entry:
                    # Use 10Y breakeven as proxy for long-end breakeven
                    implied_btp[t] = round(bcu_entry['yield'] + be_10y, 2)

        # BCU curve (5Y-30Y)
        bcu_tenors_order = ['5Y', '10Y', '20Y', '30Y']
        bcu_tenors = []
        bcu_yields = []
        if bcu:
            for t in bcu_tenors_order:
                entry = bcu.get(t)
                if isinstance(entry, dict) and 'yield' in entry:
                    bcu_tenors.append(t)
                    bcu_yields.append(entry['yield'])

        if not bcp_tenors and not bcu_tenors:
            return self._create_placeholder('Curvas Chile - sin yields')

        # Extend BCP with implied BTP
        bcp_extended_tenors = list(bcp_tenors)
        bcp_extended_yields = list(bcp_yields)
        for t in ['20Y', '30Y']:
            if t in implied_btp:
                bcp_extended_tenors.append(t)
                bcp_extended_yields.append(implied_btp[t])

        bcp_x = [self.TENOR_YEARS[t] for t in bcp_extended_tenors]
        bcu_x = [self.TENOR_YEARS[t] for t in bcu_tenors]

        fig, ax_bcu = plt.subplots(figsize=(9, 4.5))
        ax_bcp = ax_bcu.twinx()

        # BCU on left axis (real yields, lower range)
        if bcu_tenors:
            ax_bcu.plot(bcu_x, bcu_yields, color=self.COLORS['accent'], linewidth=2.5,
                        marker='D', markersize=7, label='BCU (Real UF)', zorder=3)
            for xi, yi in zip(bcu_x, bcu_yields):
                ax_bcu.text(xi, yi - 0.08, f'{yi:.2f}', ha='center', va='top',
                            fontsize=7, fontweight='bold', color=self.COLORS['accent'])

        # BCP/BTP on right axis (nominal yields, higher range)
        if bcp_extended_tenors:
            # Solid line for actual BCP
            n_actual = len(bcp_tenors)
            ax_bcp.plot(bcp_x[:n_actual], bcp_extended_yields[:n_actual],
                        color=self.SERIES_COLORS[0], linewidth=2.5,
                        marker='s', markersize=7, label='BCP (Nominal)', zorder=3)
            for xi, yi in zip(bcp_x[:n_actual], bcp_extended_yields[:n_actual]):
                ax_bcp.text(xi, yi + 0.08, f'{yi:.2f}', ha='center', va='bottom',
                            fontsize=7, fontweight='bold', color=self.SERIES_COLORS[0])

            # Dashed extension for implied BTP 20Y/30Y
            if len(bcp_x) > n_actual and n_actual > 0:
                ext_x = [bcp_x[n_actual - 1]] + bcp_x[n_actual:]
                ext_y = [bcp_extended_yields[n_actual - 1]] + bcp_extended_yields[n_actual:]
                ax_bcp.plot(ext_x, ext_y, color=self.SERIES_COLORS[0], linewidth=1.5,
                            marker='s', markersize=5, linestyle='--', alpha=0.6,
                            label='BTP impl. (BCU+BE)', zorder=3)
                for xi, yi in zip(bcp_x[n_actual:], bcp_extended_yields[n_actual:]):
                    ax_bcp.text(xi, yi + 0.08, f'{yi:.2f}*', ha='center', va='bottom',
                                fontsize=7, color=self.SERIES_COLORS[0], alpha=0.7)

        # Set axis labels & colors
        ax_bcu.set_ylabel('BCU - Yield Real (%)', fontsize=9, color=self.COLORS['accent'])
        ax_bcu.tick_params(axis='y', labelcolor=self.COLORS['accent'])
        ax_bcp.set_ylabel('BCP/BTP - Yield Nominal (%)', fontsize=9, color=self.SERIES_COLORS[0])
        ax_bcp.tick_params(axis='y', labelcolor=self.SERIES_COLORS[0])
        ax_bcp.spines['right'].set_visible(True)

        # Y-axis ranges: tight, don't start at 0
        if bcu_yields:
            bcu_min = min(bcu_yields) - 0.3
            bcu_max = max(bcu_yields) + 0.3
            ax_bcu.set_ylim(bcu_min, bcu_max)
        if bcp_extended_yields:
            bcp_min = min(bcp_extended_yields) - 0.3
            bcp_max = max(bcp_extended_yields) + 0.3
            ax_bcp.set_ylim(bcp_min, bcp_max)

        # Proportional x-axis ticks
        all_x = sorted(set(bcp_x + bcu_x))
        tenor_map = {}
        for t in bcp_extended_tenors + bcu_tenors:
            tenor_map[self.TENOR_YEARS[t]] = t
        ax_bcu.set_xticks(all_x)
        ax_bcu.set_xticklabels([tenor_map.get(x, '') for x in all_x], fontsize=9)
        ax_bcu.set_xlabel('Plazo', fontsize=9)

        # Breakevens annotation
        if breakevens:
            for tenor_key in ['5Y', '10Y']:
                be_val = breakevens.get(tenor_key)
                if be_val is None:
                    continue
                tx = self.TENOR_YEARS.get(tenor_key)
                if tx is None:
                    continue
                bcp_y = bcp.get(tenor_key, {}).get('yield') if bcp else None
                bcu_y = bcu.get(tenor_key, {}).get('yield') if bcu else None
                if bcp_y is not None and bcu_y is not None:
                    # Use BCU axis for annotation y-position (midpoint of BCU range)
                    mid_bcu = bcu_y + 0.15
                    ax_bcu.annotate(
                        f'BE {tenor_key}: {be_val:.2f}%', xy=(tx + 0.7, mid_bcu),
                        fontsize=7.5, color=self.COLORS['positive'], fontweight='bold',
                        bbox=dict(boxstyle='round,pad=0.2', facecolor='#f0fff4', alpha=0.9))

        ax_bcu.set_title('Curvas Chile: BCP/BTP (Nominal) vs BCU (Real)', fontsize=12,
                          fontweight='bold', color=self.COLORS['primary'], pad=10)

        # Combined legend
        lines1, labels1 = ax_bcu.get_legend_handles_labels()
        lines2, labels2 = ax_bcp.get_legend_handles_labels()
        ax_bcu.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=7)

        plt.tight_layout()
        return self._fig_to_base64(fig)

    # =========================================================================
    # 5. POLICY RATES — Central Bank Rate Comparison
    # =========================================================================

    def _generate_policy_rates(self) -> str:
        """Tasas de politica monetaria de bancos centrales (horizontal bar)."""
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder('Tasas de Politica Monetaria')

        policy = self._safe_val(self.data, 'chile_rates', 'policy_rates')
        tpm_current = self._safe_val(self.data, 'chile_rates', 'tpm', 'current')

        if not policy and tpm_current is None:
            return self._create_placeholder('Tasas de Politica - sin datos')

        # Build list: name, rate, color
        banks = []
        if tpm_current is not None:
            banks.append(('BCCh (TPM)', tpm_current, self.EM_COLORS['tpm']))
        if policy:
            bank_map = [
                ('fed', 'Fed', self.DM_COLORS['fed']),
                ('ecb', 'ECB', self.DM_COLORS['ecb']),
                ('boj', 'BoJ', self.DM_COLORS['boj']),
                ('boe', 'BoE', self.DM_COLORS['boe']),
                ('pboc', 'PBoC', self.EM_COLORS['pboc']),
                ('bcb', 'BCB (Brasil)', self.EM_COLORS['bcb']),
                ('banxico', 'Banxico', self.EM_COLORS['banxico']),
            ]
            for key, label, color in bank_map:
                rate = policy.get(key)
                if rate is not None:
                    banks.append((label, rate, color))

        if not banks:
            return self._create_placeholder('Tasas de Politica - sin datos')

        # Sort by rate
        banks.sort(key=lambda x: x[1])

        labels = [b[0] for b in banks]
        rates = [b[1] for b in banks]
        colors = [b[2] for b in banks]

        fig, ax = plt.subplots(figsize=(8, max(3.5, 0.5 * len(banks) + 1)))

        y = np.arange(len(banks))
        bars = ax.barh(y, rates, color=colors, alpha=0.85, height=0.6)

        for bar, rate in zip(bars, rates):
            w = bar.get_width()
            ax.text(w + 0.15, bar.get_y() + bar.get_height() / 2,
                    f'{rate:.2f}%', va='center', fontsize=9, fontweight='bold',
                    color=self.COLORS['text_dark'])

        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=9)
        ax.set_xlabel('Tasa (%)', fontsize=9)
        ax.set_title('Tasas de Politica Monetaria - Bancos Centrales', fontsize=12,
                      fontweight='bold', color=self.COLORS['primary'], pad=10)

        # Legend for DM/EM
        dm_patch = mpatches.Patch(color=self.DM_COLORS['fed'], label='Desarrollados', alpha=0.85)
        em_patch = mpatches.Patch(color=self.EM_COLORS['bcb'], label='Emergentes', alpha=0.85)
        ax.legend(handles=[dm_patch, em_patch], loc='lower right', fontsize=8)

        plt.tight_layout()
        return self._fig_to_base64(fig)

    # =========================================================================
    # 6. FED EXPECTATIONS — Market path vs Fed Dots
    # =========================================================================

    def _generate_fed_expectations(self) -> str:
        """Trayectoria esperada de la Fed: mercado vs dots."""
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder('Expectativas Fed')

        meetings = self._safe_val(self.data, 'fed_expectations', 'meetings')
        comparison = self._safe_val(self.data, 'fed_dots', 'comparison')
        current_rate = self._safe_val(self.data, 'fed_expectations', 'current_rate')

        if not meetings:
            return self._create_placeholder('Expectativas Fed - sin datos')

        fig, ax = plt.subplots(figsize=(9, 4.5))

        # Market expectations path
        labels = [m['label'] for m in meetings]
        expected_rates = [m['expected_rate'] for m in meetings]

        x = np.arange(len(labels))
        ax.plot(x, expected_rates, color=self.SERIES_COLORS[0], linewidth=2.5,
                marker='o', markersize=5, label='Mercado (SOFR)', zorder=3)

        # Current rate line
        if current_rate is not None:
            ax.axhline(y=current_rate, color=self.COLORS['text_light'],
                       linewidth=1, linestyle=':', alpha=0.7,
                       label=f'Tasa actual: {current_rate:.2f}%')

        # Fed dots overlay
        if comparison:
            dots_by_year = self._safe_val(self.data, 'fed_dots', 'fed_dots', 'by_year')
            if dots_by_year:
                dot_labels = []
                dot_rates = []
                dot_x_pos = []
                for comp in comparison:
                    horizon = comp.get('horizon', '')
                    dot_rate = comp.get('fed_dots')
                    if dot_rate is not None:
                        # Find matching x position (approximate)
                        year_str = horizon.replace('End ', '').replace('Longer Run', '')
                        # Map to meeting labels
                        match_idx = None
                        for i, lbl in enumerate(labels):
                            if year_str and year_str in lbl:
                                match_idx = i
                                break
                        if match_idx is None and 'Dec' in str(labels):
                            # Use last meeting of that year
                            for i, lbl in enumerate(labels):
                                if 'Dec' in lbl:
                                    match_idx = i
                        if match_idx is not None:
                            dot_labels.append(horizon)
                            dot_rates.append(dot_rate)
                            dot_x_pos.append(match_idx)

                if dot_x_pos:
                    ax.plot(dot_x_pos, dot_rates, color=self.COLORS['accent'],
                            linewidth=2, linestyle='--', marker='D', markersize=6,
                            label='Fed Dots (Mediana)', zorder=3, alpha=0.85)

                    # Shade area between
                    if len(dot_x_pos) >= 2:
                        # Build matching market rates at dot positions
                        market_at_dots = [expected_rates[i] for i in dot_x_pos]
                        ax.fill_between(dot_x_pos, dot_rates, market_at_dots,
                                        alpha=0.1, color=self.COLORS['accent'])

        # Terminal rate annotation
        summary = self._safe_val(self.data, 'fed_expectations', 'summary')
        if summary:
            terminal = summary.get('terminal_rate')
            if terminal is not None:
                ax.text(0.98, 0.98, f'Terminal: {terminal:.2f}%',
                        transform=ax.transAxes, ha='right', va='top',
                        fontsize=9, fontweight='bold', color=self.COLORS['accent'],
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='#fffff0', alpha=0.9))

        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=8, rotation=45, ha='right')
        ax.set_ylabel('Tasa (%)', fontsize=9)
        ax.set_title('Expectativas de Tasa Fed: Mercado vs Dots', fontsize=12,
                      fontweight='bold', color=self.COLORS['primary'], pad=10)
        ax.legend(loc='upper right', fontsize=7)
        plt.tight_layout()
        return self._fig_to_base64(fig)

    # =========================================================================
    # 7. TPM EXPECTATIONS — TPM Rate Path (step line)
    # =========================================================================

    def _generate_tpm_expectations(self) -> str:
        """Trayectoria esperada de la TPM (step line)."""
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder('Expectativas TPM')

        meetings = self._safe_val(self.data, 'tpm_expectations', 'meetings')
        current_rate = self._safe_val(self.data, 'tpm_expectations', 'current_rate')
        summary = self._safe_val(self.data, 'tpm_expectations', 'summary')

        if not meetings:
            return self._create_placeholder('Expectativas TPM - sin datos')

        fig, ax = plt.subplots(figsize=(9, 4.5))

        labels = [m['label'] for m in meetings]
        expected_rates = [m['expected_rate'] for m in meetings]

        x = np.arange(len(labels))

        # Step-line chart
        ax.step(x, expected_rates, where='mid', color=self.COLORS['accent'],
                linewidth=2.5, label='TPM Esperada (SPC)', zorder=3)
        ax.plot(x, expected_rates, 'o', color=self.COLORS['accent'],
                markersize=5, zorder=4)

        # Current rate line
        if current_rate is not None:
            ax.axhline(y=current_rate, color=self.COLORS['text_light'],
                       linewidth=1.5, linestyle=':', alpha=0.7,
                       label=f'TPM actual: {current_rate:.2f}%')
            # Mark current
            ax.plot(-0.5, current_rate, '>', color=self.COLORS['negative'],
                    markersize=10, zorder=5, clip_on=False)

        # Annotate meeting rates
        for i, (lbl, rate) in enumerate(zip(labels, expected_rates)):
            ax.text(i, rate + 0.06, f'{rate:.2f}%', ha='center', va='bottom',
                    fontsize=7, fontweight='bold', color=self.COLORS['text_dark'])

        # Summary box
        if summary:
            direction = summary.get('direction', '')
            terminal = summary.get('tasa_terminal')
            cuts = summary.get('recortes_esperados', 0)
            info_parts = []
            if direction:
                info_parts.append(f'Direccion: {direction}')
            if cuts:
                info_parts.append(f'Recortes: {cuts}')
            if terminal is not None:
                info_parts.append(f'Terminal: {terminal:.2f}%')
            if info_parts:
                info_text = ' | '.join(info_parts)
                ax.text(0.5, -0.15, info_text, transform=ax.transAxes,
                        ha='center', fontsize=8, color=self.COLORS['text_light'],
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))

        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=8, rotation=45, ha='right')
        ax.set_ylabel('Tasa (%)', fontsize=9)
        ax.set_title('Expectativas de TPM Chile', fontsize=12,
                      fontweight='bold', color=self.COLORS['primary'], pad=10)
        ax.legend(loc='upper right', fontsize=8)
        ax.set_xlim(-0.5, len(labels) - 0.5)
        plt.tight_layout()
        return self._fig_to_base64(fig)

    # =========================================================================
    # 8. INTERNATIONAL YIELDS — 10Y Yields Global (horizontal bar)
    # =========================================================================

    def _generate_intl_yields(self) -> str:
        """Yields 10Y globales coloreados DM vs EM con spread vs USA."""
        if not MATPLOTLIB_AVAILABLE:
            return self._create_placeholder('Yields Internacionales 10Y')

        intl = self.data.get('international_yields')
        if not intl or 'error' in intl:
            return self._create_placeholder('Yields Internacionales - sin datos')

        country_order = [
            ('usa', 'EE.UU.'), ('germany', 'Alemania'), ('uk', 'Reino Unido'),
            ('japan', 'Japon'), ('brazil', 'Brasil'), ('mexico', 'Mexico'),
            ('colombia', 'Colombia'), ('peru', 'Peru'),
        ]

        labels = []
        yields_10y = []
        spreads = []
        colors = []

        for key, label in country_order:
            entry = intl.get(key)
            if not isinstance(entry, dict):
                continue
            y10 = entry.get('yield_10y')
            if y10 is None:
                continue
            labels.append(label)
            yields_10y.append(y10)
            spreads.append(entry.get('spread_vs_usa'))
            # Color by DM/EM
            if key in self.DM_COLORS:
                colors.append(self.DM_COLORS[key])
            elif key in self.EM_COLORS:
                colors.append(self.EM_COLORS[key])
            else:
                colors.append(self.COLORS['text_medium'])

        if not labels:
            return self._create_placeholder('Yields Internacionales - sin datos')

        fig, ax = plt.subplots(figsize=(8, max(3.5, 0.5 * len(labels) + 1)))

        y = np.arange(len(labels))
        bars = ax.barh(y, yields_10y, color=colors, alpha=0.85, height=0.6)

        for i, (bar, yld, spread) in enumerate(zip(bars, yields_10y, spreads)):
            w = bar.get_width()
            text = f'{yld:.2f}%'
            if spread is not None:
                text += f' ({spread:+.0f}bp vs US)'
            ax.text(w + 0.1, bar.get_y() + bar.get_height() / 2,
                    text, va='center', fontsize=7,
                    color=self.COLORS['text_medium'])

        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=9)
        ax.set_xlabel('Yield 10Y (%)', fontsize=9)
        ax.set_title('Yields 10Y Globales', fontsize=12, fontweight='bold',
                      color=self.COLORS['primary'], pad=10)

        dm_patch = mpatches.Patch(color=self.DM_COLORS['fed'], label='Desarrollados', alpha=0.85)
        em_patch = mpatches.Patch(color=self.EM_COLORS['bcb'], label='Emergentes', alpha=0.85)
        ax.legend(handles=[dm_patch, em_patch], loc='lower right', fontsize=8)

        ax.invert_yaxis()
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

    # Buscar rf data mas reciente
    rf_dir = Path(__file__).parent / "output" / "rf_data"
    rf_files = sorted(rf_dir.glob("rf_data_*.json"), reverse=True)

    if rf_files:
        print(f"[INFO] Cargando: {rf_files[0].name}")
        with open(rf_files[0], 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        print("[WARN] Sin rf data - usando dict vacio")
        data = {}

    gen = RFChartsGenerator(data)
    charts = gen.generate_all_charts()

    print(f"\nCharts generados: {len(charts)}")
    for k, v in charts.items():
        is_img = v.startswith('data:image') if v else False
        size = len(v) if v else 0
        print(f"  {k}: {size:,} chars, es_imagen={is_img}")
