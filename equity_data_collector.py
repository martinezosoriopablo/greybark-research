# -*- coding: utf-8 -*-
"""
Greybark Research - Equity Data Collector
==========================================

Orquestador cuantitativo para el reporte de Renta Variable.
Recopila datos REALES de múltiples fuentes usando los módulos existentes
de la biblioteca greybark.

Fuentes de datos:
- yfinance: Precios, valuaciones (P/E, P/B, dividendos), retornos de ETFs
- EarningsAnalytics (AlphaVantage): Beat rates, EPS growth, implied growth
- MarketBreadthAnalytics (yfinance): Sector breadth, risk appetite, cycle
- RiskMetrics (yfinance): Correlaciones, VaR, drawdowns
- FactorAnalytics (AV + yfinance): Factor scores por región
- InflationAnalytics (FRED): Real rates para ERP calculation
- CreditSpreadAnalytics (FRED): IG/HY spreads, señales de rotación

Patrón: try/except por módulo, falla silenciosa con {'error': str(e)}.
Misma arquitectura que council_data_collector.py.

Uso:
    collector = EquityDataCollector(verbose=True)
    data = collector.collect_all()
    # data se pasa a RVContentGenerator(market_data=data)
"""

import sys
import os
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Fix Windows console encoding for library modules that use unicode
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        pass

# Agregar paths para imports
sys.path.insert(0, str(Path(__file__).parent))
LIB_PATH = Path(__file__).parent
sys.path.insert(0, str(LIB_PATH))

# =========================================================================
# CONFIGURACIÓN DE UNIVERSO
# =========================================================================

# ETFs regionales para valuaciones y retornos
REGIONAL_ETFS = {
    'us': {'ticker': 'SPY', 'name': 'S&P 500'},
    'europe': {'ticker': 'EFA', 'name': 'EAFE (Europa/Japón)'},
    'em': {'ticker': 'EEM', 'name': 'Mercados Emergentes'},
    'japan': {'ticker': 'EWJ', 'name': 'Japón'},
    'china': {'ticker': 'MCHI', 'name': 'China'},
    'latam': {'ticker': 'ILF', 'name': 'LatAm 40'},
    'chile': {'ticker': 'ECH', 'name': 'Chile'},
    'brazil': {'ticker': 'EWZ', 'name': 'Brasil'},
}

# Sector ETFs (SPDR S&P 500)
SECTOR_ETFS = {
    'technology': {'ticker': 'XLK', 'name': 'Tecnología'},
    'healthcare': {'ticker': 'XLV', 'name': 'Salud'},
    'financials': {'ticker': 'XLF', 'name': 'Financiero'},
    'consumer_disc': {'ticker': 'XLY', 'name': 'Consumo Disc.'},
    'industrials': {'ticker': 'XLI', 'name': 'Industriales'},
    'energy': {'ticker': 'XLE', 'name': 'Energía'},
    'materials': {'ticker': 'XLB', 'name': 'Materiales'},
    'utilities': {'ticker': 'XLU', 'name': 'Utilities'},
    'real_estate': {'ticker': 'XLRE', 'name': 'Real Estate'},
    'comm_services': {'ticker': 'XLC', 'name': 'Comunicaciones'},
    'consumer_staples': {'ticker': 'XLP', 'name': 'Consumo Básico'},
}

# Representativos por región para earnings (1 blue chip por sector/región)
EARNINGS_UNIVERSE = {
    'us_mega': ['AAPL', 'MSFT', 'AMZN', 'NVDA', 'GOOGL', 'META', 'JPM', 'UNH'],
    'europe': ['ASML', 'SAP', 'NVO'],
    'chile': ['SQM', 'BSAC', 'BCH', 'LTM', 'CCU'],
}

# Índices para correlaciones
CORRELATION_UNIVERSE = ['SPY', 'EFA', 'EEM', 'EWJ', 'ECH', 'EWZ', 'MCHI', 'GLD', 'TLT', 'HYG']


class EquityDataCollector:
    """Orquestador de datos cuantitativos para Renta Variable."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.data = {}
        self.errors = []

    def _print(self, msg: str):
        if self.verbose:
            print(msg)

    def _safe_float(self, val, default=None):
        """Convierte a float de forma segura."""
        if val is None:
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    # =========================================================================
    # 1. VALUACIONES REGIONALES (yfinance)
    # =========================================================================

    def collect_regional_valuations(self) -> Dict[str, Any]:
        """
        Obtiene valuaciones de ETFs regionales via yfinance.

        Datos: P/E trailing, P/E forward, P/B, dividend yield,
        retornos (1M, 3M, YTD, 1Y), precio actual.

        Fuente: yfinance (Yahoo Finance API)
        """
        self._print("  -> Valuaciones regionales (yfinance)...")

        try:
            import yfinance as yf
        except ImportError:
            return {'error': 'yfinance not installed'}

        results = {}

        for region_key, etf_info in REGIONAL_ETFS.items():
            ticker = etf_info['ticker']
            try:
                stock = yf.Ticker(ticker)
                info = stock.info

                # Precio y retornos
                hist = stock.history(period='1y', timeout=30)
                if hist.empty:
                    results[region_key] = {'error': f'No data for {ticker}'}
                    continue

                current_price = hist['Close'].iloc[-1]

                # Retornos
                returns = {}
                if len(hist) >= 22:
                    returns['1m'] = ((current_price / hist['Close'].iloc[-22]) - 1) * 100
                if len(hist) >= 63:
                    returns['3m'] = ((current_price / hist['Close'].iloc[-63]) - 1) * 100
                if len(hist) >= 126:
                    returns['6m'] = ((current_price / hist['Close'].iloc[-126]) - 1) * 100
                if len(hist) >= 252:
                    returns['1y'] = ((current_price / hist['Close'].iloc[-1 * min(252, len(hist))]) - 1) * 100

                # YTD
                ytd_cutoff = pd.Timestamp(f'{datetime.now().year}-01-01').tz_localize(hist.index.tz)
                ytd_start = hist.loc[hist.index >= ytd_cutoff]
                if not ytd_start.empty:
                    returns['ytd'] = ((current_price / ytd_start['Close'].iloc[0]) - 1) * 100

                # Valuaciones del info dict
                results[region_key] = {
                    'ticker': ticker,
                    'name': etf_info['name'],
                    'price': round(current_price, 2),
                    'pe_trailing': self._safe_float(info.get('trailingPE')),
                    'pe_forward': self._safe_float(info.get('forwardPE')),
                    'pb': self._safe_float(info.get('priceToBook')),
                    'dividend_yield': self._safe_float(info.get('dividendYield', 0)) * 100 if info.get('dividendYield') and self._safe_float(info.get('dividendYield', 0)) < 1 else (self._safe_float(info.get('dividendYield')) if info.get('dividendYield') else None),
                    'returns': {k: round(v, 2) for k, v in returns.items()},
                    'fifty_two_week_high': self._safe_float(info.get('fiftyTwoWeekHigh')),
                    'fifty_two_week_low': self._safe_float(info.get('fiftyTwoWeekLow')),
                    'market_cap': self._safe_float(info.get('totalAssets')),  # ETFs use totalAssets
                    'source': 'yfinance',
                    'as_of': hist.index[-1].strftime('%Y-%m-%d'),
                }
                self._print(f"    [OK] {ticker} ({region_key}): P/E={results[region_key]['pe_trailing']}, "
                           f"1M={returns.get('1m', 'N/A'):.1f}%" if isinstance(returns.get('1m'), (int, float)) else f"    [OK] {ticker}")

            except Exception as e:
                results[region_key] = {'error': str(e), 'ticker': ticker}
                self._print(f"    [ERR] {ticker}: {e}")

        return results

    # =========================================================================
    # 2. ANÁLISIS SECTORIAL (yfinance + breadth)
    # =========================================================================

    def collect_sector_data(self) -> Dict[str, Any]:
        """
        Combina datos sectoriales de yfinance (retornos) + MarketBreadthAnalytics.

        Datos: retornos sectoriales, breadth (% > 50MA), risk appetite,
        cyclical/defensive ratio, size factor.

        Fuentes: yfinance + greybark.analytics.breadth.market_breadth
        """
        self._print("  -> Datos sectoriales (yfinance + breadth)...")

        result = {
            'sector_returns': {},
            'breadth': {},
        }

        # 2a. Retornos sectoriales via yfinance
        try:
            import yfinance as yf

            for sector_key, etf_info in SECTOR_ETFS.items():
                ticker = etf_info['ticker']
                try:
                    hist = yf.Ticker(ticker).history(period='1y')
                    if hist.empty:
                        continue

                    current = hist['Close'].iloc[-1]
                    returns = {}
                    if len(hist) >= 22:
                        returns['1m'] = round(((current / hist['Close'].iloc[-22]) - 1) * 100, 2)
                    if len(hist) >= 63:
                        returns['3m'] = round(((current / hist['Close'].iloc[-63]) - 1) * 100, 2)
                    if len(hist) >= 252:
                        returns['1y'] = round(((current / hist['Close'].iloc[-1 * min(252, len(hist))]) - 1) * 100, 2)

                    # YTD
                    ytd_cutoff = pd.Timestamp(f'{datetime.now().year}-01-01').tz_localize(hist.index.tz)
                    ytd_start = hist.loc[hist.index >= ytd_cutoff]
                    if not ytd_start.empty:
                        returns['ytd'] = round(((current / ytd_start['Close'].iloc[0]) - 1) * 100, 2)

                    result['sector_returns'][sector_key] = {
                        'ticker': ticker,
                        'name': etf_info['name'],
                        'price': round(current, 2),
                        'returns': returns,
                        'source': 'yfinance',
                    }
                except Exception as e:
                    result['sector_returns'][sector_key] = {'error': str(e)}

        except ImportError:
            result['sector_returns'] = {'error': 'yfinance not installed'}

        # 2b. Market Breadth Analytics
        try:
            from greybark.analytics.breadth.market_breadth import MarketBreadthAnalytics
            breadth = MarketBreadthAnalytics()
            dashboard = breadth.get_breadth_dashboard()

            result['breadth'] = {
                'sector_breadth': dashboard.get('sector_breadth', {}),
                'risk_appetite': dashboard.get('risk_appetite', {}),
                'cyclical_defensive': dashboard.get('cyclical_defensive', {}),
                'size_factor': dashboard.get('size_factor', {}),
                'summary': dashboard.get('summary', {}),
                'source': 'greybark.market_breadth (yfinance)',
            }
            self._print(f"    [OK] Breadth dashboard: {result['breadth'].get('summary', {}).get('signal', 'N/A')}")
        except Exception as e:
            result['breadth'] = {'error': str(e)}
            self._print(f"    [ERR] Breadth: {e}")

        return result

    # =========================================================================
    # 3. CORRELACIONES Y RIESGO (risk/metrics)
    # =========================================================================

    def collect_risk_correlations(self) -> Dict[str, Any]:
        """
        Calcula correlaciones reales y métricas de riesgo.

        Datos: matriz de correlaciones (10 activos), VaR, CVaR,
        drawdowns, diversification score.

        Fuente: greybark.analytics.risk.metrics (yfinance bajo el capó)
        """
        self._print("  -> Correlaciones y riesgo (risk/metrics)...")

        try:
            from greybark.analytics.risk.metrics import RiskMetrics, fetch_returns

            # Descargar retornos
            returns = fetch_returns(CORRELATION_UNIVERSE, period='2y')

            if returns.empty:
                return {'error': 'No returns data fetched'}

            # Correlación actual (últimos 6 meses)
            recent_returns = returns.tail(126)  # ~6 meses
            corr_matrix = recent_returns.corr()

            # Convertir a dict serializable
            corr_dict = {}
            for col in corr_matrix.columns:
                corr_dict[col] = {row: round(corr_matrix.loc[row, col], 3)
                                  for row in corr_matrix.index}

            # Métricas de riesgo con portfolio default equity
            equity_weights = {
                'SPY': 0.35, 'EFA': 0.20, 'EEM': 0.15,
                'EWJ': 0.05, 'ECH': 0.05, 'EWZ': 0.05,
                'MCHI': 0.05, 'GLD': 0.05, 'TLT': 0.05,
            }

            # Filtrar weights a los activos disponibles en returns
            available = [t for t in equity_weights if t in returns.columns]
            weights_filtered = {t: equity_weights[t] for t in available}
            total_w = sum(weights_filtered.values())
            weights_filtered = {t: w / total_w for t, w in weights_filtered.items()}

            rm = RiskMetrics(returns[list(weights_filtered.keys())], weights_filtered)

            # VaR y drawdown
            var_data = rm.calculate_all_var()
            dd_data = rm.drawdown_analysis()

            var_95_raw = var_data.get('var_95_historical')
            var_99_raw = var_data.get('var_99_historical')
            es_95_raw = var_data.get('es_95')
            dd_max_raw = dd_data.get('max_drawdown')
            dd_cur_raw = dd_data.get('current_drawdown')

            result = {
                'correlation_matrix': corr_dict,
                'correlation_period': f'{recent_returns.index[0].strftime("%Y-%m-%d")} to {recent_returns.index[-1].strftime("%Y-%m-%d")}',
                'var_95_daily': round(var_95_raw * 100, 3) if var_95_raw is not None else None,
                'var_99_daily': round(var_99_raw * 100, 3) if var_99_raw is not None else None,
                'cvar_95': round(es_95_raw * 100, 3) if es_95_raw is not None else None,
                'max_drawdown': round(dd_max_raw * 100, 2) if dd_max_raw is not None else None,
                'current_drawdown': round(dd_cur_raw * 100, 2) if dd_cur_raw is not None else None,
                'diversification_score': round(rm.diversification_score(), 3),
                'source': 'greybark.risk.metrics (yfinance)',
            }

            # Sanity check: VaR values outside [0.01, 15.0]% are likely errors
            for k in ('var_95_daily', 'var_99_daily', 'cvar_95'):
                v = result.get(k)
                if v is not None and (abs(v) < 0.01 or abs(v) > 15.0):
                    logger.warning(f"VaR sanity fail: {k}={v}% out of range [0.01-15.0], setting None")
                    result[k] = None

            # VIX actual
            try:
                import yfinance as yf
                vix = yf.Ticker('^VIX')
                vix_hist = vix.history(period='1y')
                if not vix_hist.empty:
                    vix_current = vix_hist['Close'].iloc[-1]
                    vix_avg_1y = vix_hist['Close'].mean()
                    vix_high = vix_hist['Close'].max()
                    vix_low = vix_hist['Close'].min()
                    result['vix'] = {
                        'current': round(vix_current, 2),
                        'avg_1y': round(vix_avg_1y, 2),
                        'high_1y': round(vix_high, 2),
                        'low_1y': round(vix_low, 2),
                        'as_of': vix_hist.index[-1].strftime('%Y-%m-%d'),
                    }
                    self._print(f"    [OK] VIX: {vix_current:.1f} (avg 1Y: {vix_avg_1y:.1f})")
            except Exception as e:
                self._print(f"    [WARN] VIX: {e}")

            var95_str = f"{result['var_95_daily']}%" if result['var_95_daily'] is not None else "N/D"
            self._print(f"    [OK] Correlación: {len(corr_dict)} activos, "
                        f"VaR95={var95_str}")
            return result

        except Exception as e:
            self._print(f"    [ERR] Risk: {e}")
            return {'error': str(e)}

    # =========================================================================
    # 4. EARNINGS (AlphaVantage)
    # =========================================================================

    def collect_earnings_data(self) -> Dict[str, Any]:
        """
        Recopila datos de earnings usando EarningsAnalytics.

        Datos: Beat rates, EPS growth, surprise %, analyst estimates,
        revision trends, margins/ROE por grupo (US mega, Europe, Chile).

        Fuente: greybark.analytics.earnings (AlphaVantage Premium)
        Nota: AlphaVantage tiene rate limits (75 calls/min Premium).
              ~45 calls total: 13 EARNINGS + 13 EARNINGS_ESTIMATES + 13 OVERVIEW + 5 INCOME + 1 CALENDAR
        """
        self._print("  -> Datos de earnings (AlphaVantage)...")

        try:
            from greybark.analytics.earnings.earnings_analytics import EarningsAnalytics
            ea = EarningsAnalytics()

            result = {}

            # Tickers representativos para income statement (1-2 por grupo)
            income_tickers = {'AAPL', 'MSFT', 'ASML', 'SQM'}

            for group_name, tickers in EARNINGS_UNIVERSE.items():
                group_data = []
                for ticker in tickers:
                    try:
                        # 1. Earnings history (EARNINGS endpoint)
                        report = ea.get_earnings_history(ticker)
                        stock_data = {'ticker': ticker}

                        if 'error' not in report:
                            track = report.get('track_record', {})
                            annual = report.get('annual_eps', {})
                            eps_growth = annual.get('yoy_growth_pct')
                            # Cap extreme EPS growth outliers (e.g. low-base effect)
                            if eps_growth is not None and abs(eps_growth) > 500:
                                logger.warning(f"EPS growth outlier {ticker}: {eps_growth:.0f}%, capping to None")
                                eps_growth = None

                            stock_data.update({
                                'beat_rate': track.get('beat_rate_pct'),
                                'avg_surprise': track.get('avg_surprise_pct'),
                                'eps_growth_yoy': eps_growth,
                                'quarters_analyzed': len(report.get('quarterly_earnings', [])),
                            })
                            self._print(f"    [OK] {ticker}: beat={track.get('beat_rate_pct', 'N/A')}%")

                        # 2. Analyst estimates (EARNINGS_ESTIMATES endpoint)
                        try:
                            estimates = ea.get_analyst_estimates(ticker)
                            if 'error' not in estimates:
                                rev = estimates.get('revision_summary', {})
                                stock_data.update({
                                    'forward_eps': estimates.get('forward_eps'),
                                    'revision_up_30d': rev.get('upgrades_30d', 0),
                                    'revision_down_30d': rev.get('downgrades_30d', 0),
                                    'upgrade_pct_30d': rev.get('upgrade_pct_30d'),
                                    'revision_status': rev.get('status'),
                                    'avg_eps_change_30d_pct': rev.get('avg_eps_change_30d_pct'),
                                    'estimates_source': estimates.get('source', 'OVERVIEW'),
                                })
                                self._print(f"    [OK] {ticker} estimates: {rev.get('status', 'N/A')}")
                        except Exception as e:
                            self._print(f"    [WARN] {ticker} estimates: {e}")

                        # 3. Fundamentals (OVERVIEW endpoint) — margins, ROE, analyst target
                        try:
                            fundamentals = ea.get_fundamentals_summary(ticker)
                            if 'error' not in fundamentals:
                                stock_data.update({
                                    'profit_margin': fundamentals.get('profit_margin'),
                                    'operating_margin': fundamentals.get('operating_margin'),
                                    'roe': fundamentals.get('roe'),
                                    'trailing_pe': fundamentals.get('trailing_pe'),
                                    'forward_pe': fundamentals.get('forward_pe'),
                                    'analyst_target': fundamentals.get('analyst_target_price'),
                                    'analyst_buy_pct': fundamentals.get('analyst_ratings', {}).get('buy_pct'),
                                })
                        except Exception as e:
                            self._print(f"    [WARN] {ticker} fundamentals: {e}")

                        # 4. Income statement (INCOME_STATEMENT) — only for representative tickers
                        if ticker in income_tickers:
                            try:
                                income = ea.get_income_statement(ticker)
                                if 'error' not in income:
                                    stock_data.update({
                                        'gross_margin': income.get('gross_margin'),
                                        'net_margin_q': income.get('net_margin'),
                                        'revenue_growth_yoy': income.get('revenue_growth_yoy'),
                                    })
                                    self._print(f"    [OK] {ticker} income: margin={income.get('operating_margin')}%")
                            except Exception as e:
                                self._print(f"    [WARN] {ticker} income: {e}")

                        group_data.append(stock_data)

                    except Exception as e:
                        self._print(f"    [ERR] {ticker}: {e}")
                        continue

                # Agregar promedios del grupo
                if group_data:
                    def _avg(key):
                        vals = [d[key] for d in group_data if d.get(key) is not None]
                        return round(sum(vals) / len(vals), 2) if vals else None

                    result[group_name] = {
                        'stocks': group_data,
                        'avg_beat_rate': _avg('beat_rate'),
                        'avg_surprise_pct': _avg('avg_surprise'),
                        'avg_eps_growth_yoy': _avg('eps_growth_yoy'),
                        'avg_revision_up_30d': _avg('revision_up_30d'),
                        'avg_revision_down_30d': _avg('revision_down_30d'),
                        'avg_upgrade_pct_30d': _avg('upgrade_pct_30d'),
                        'avg_eps_change_30d_pct': _avg('avg_eps_change_30d_pct'),
                        'avg_profit_margin': _avg('profit_margin'),
                        'avg_operating_margin': _avg('operating_margin'),
                        'avg_roe': _avg('roe'),
                        'avg_trailing_pe': _avg('trailing_pe'),
                        'avg_forward_pe': _avg('forward_pe'),
                        'source': 'greybark.earnings_analytics (AlphaVantage)',
                    }
                else:
                    result[group_name] = {'error': 'No earnings data retrieved'}

            # 5. Earnings calendar
            try:
                calendar = ea.get_upcoming_earnings(
                    '3month',
                    filter_symbols=[t for tickers in EARNINGS_UNIVERSE.values() for t in tickers]
                )
                if 'error' not in calendar:
                    result['calendar'] = calendar
                    self._print(f"    [OK] Calendar: {calendar.get('filtered_entries', 0)} upcoming")
            except Exception as e:
                self._print(f"    [WARN] Calendar: {e}")

            return result

        except Exception as e:
            self._print(f"    [ERR] Earnings: {e}")
            return {'error': str(e)}

    # =========================================================================
    # 5. FACTOR PERFORMANCE (AlphaVantage + yfinance)
    # =========================================================================

    def collect_factor_data(self) -> Dict[str, Any]:
        """
        Calcula factor scores para ETFs clave.

        Factores: Value, Growth, Momentum, Quality (0-100 cada uno).

        Fuente: greybark.analytics.factors (AlphaVantage + yfinance)
        Nota: Limitado a unos pocos tickers por rate limits AV.
        """
        self._print("  -> Factor analysis (AV + yfinance)...")

        try:
            from greybark.analytics.factors.factor_analytics import FactorAnalytics
            fa = FactorAnalytics()

            # Factor scores para los principales ETFs regionales
            factor_tickers = ['SPY', 'EFA', 'EEM', 'EWJ', 'ECH']
            result = {}

            for ticker in factor_tickers:
                try:
                    profile = fa.get_factor_profile(ticker)
                    if 'error' not in profile:
                        result[ticker] = {
                            'value': profile.get('value_score'),
                            'growth': profile.get('growth_score'),
                            'momentum': profile.get('momentum_score'),
                            'quality': profile.get('quality_score'),
                            'composite': profile.get('composite_score'),
                            'source': 'greybark.factor_analytics',
                        }
                        self._print(f"    [OK] {ticker}: composite={profile.get('composite_score', 'N/A')}")
                except Exception as e:
                    result[ticker] = {'error': str(e)}
                    self._print(f"    [ERR] {ticker}: {e}")

            return result

        except Exception as e:
            self._print(f"    [ERR] Factors: {e}")
            return {'error': str(e)}

    # =========================================================================
    # 6. REAL RATES & ERP (FRED via InflationAnalytics)
    # =========================================================================

    def collect_real_rates(self) -> Dict[str, Any]:
        """
        Obtiene tasas reales para cálculo de Equity Risk Premium.

        ERP = Earnings Yield (1/PE) - Real Rate (TIPS 10Y)

        Datos: Breakeven inflation, real rates, ERP estimado.
        Fuente: greybark.analytics.macro.inflation_analytics (FRED)
        """
        self._print("  -> Tasas reales y ERP (FRED)...")

        try:
            from greybark.analytics.macro.inflation_analytics import InflationAnalytics
            ia = InflationAnalytics()

            # Breakeven y real rates
            breakeven = ia.get_breakeven_inflation()
            real_rates = ia.get_real_rates()

            # Extraer de estructura anidada correcta
            be_current = breakeven.get('current', {})
            rr_current = real_rates.get('current', {})

            result = {
                'breakeven_5y': be_current.get('breakeven_5y'),
                'breakeven_10y': be_current.get('breakeven_10y'),
                'breakeven_status': breakeven.get('status'),
                'real_rate_5y': rr_current.get('tips_5y'),
                'real_rate_10y': rr_current.get('tips_10y'),
                'real_rate_status': real_rates.get('policy_stance'),
                'source': 'greybark.inflation_analytics (FRED)',
            }

            # Calcular ERP si tenemos datos de valuación de SPY
            spy_pe = None
            try:
                import yfinance as yf
                spy_info = yf.Ticker('SPY').info
                spy_pe = self._safe_float(spy_info.get('trailingPE'))
            except Exception:
                pass

            if spy_pe and result.get('real_rate_10y') is not None:
                earnings_yield = (1 / spy_pe) * 100  # En %
                erp = earnings_yield - result['real_rate_10y']
                result['spy_earnings_yield'] = round(earnings_yield, 2)
                result['equity_risk_premium'] = round(erp, 2)

                # Interpretar ERP
                if erp > 4.0:
                    result['erp_signal'] = 'ATRACTIVO'
                elif erp > 2.5:
                    result['erp_signal'] = 'NEUTRAL'
                else:
                    result['erp_signal'] = 'CARO'

                self._print(f"    [OK] ERP: {erp:.2f}% (EY={earnings_yield:.2f}% - RR={result['real_rate_10y']:.2f}%)")

            return result

        except Exception as e:
            self._print(f"    [ERR] Real rates: {e}")
            return {'error': str(e)}

    # =========================================================================
    # 7. CREDIT SPREADS (FRED)
    # =========================================================================

    def collect_credit_spreads(self) -> Dict[str, Any]:
        """
        Obtiene spreads de crédito como indicador de riesgo equity.

        Datos: IG/HY spreads, percentiles, señal de rotación de calidad.
        Fuente: greybark.analytics.credit.credit_spreads (FRED)
        """
        self._print("  -> Credit spreads (FRED)...")

        try:
            from greybark.analytics.credit.credit_spreads import CreditSpreadAnalytics
            csa = CreditSpreadAnalytics()

            dashboard = csa.get_credit_dashboard()

            ig = dashboard.get('ig_breakdown', {}).get('total', {})
            hy = dashboard.get('hy_breakdown', {}).get('total', {})

            result = {
                'ig_spread': ig.get('current_bps'),
                'ig_percentile': ig.get('percentile_5y'),
                'ig_signal': ig.get('level'),
                'hy_spread': hy.get('current_bps'),
                'hy_percentile': hy.get('percentile_5y'),
                'hy_signal': hy.get('level'),
                'quality_rotation': dashboard.get('quality_rotation', {}),
                'summary': dashboard.get('summary', {}),
                'source': 'greybark.credit_spreads (FRED)',
            }

            self._print(f"    [OK] IG={result.get('ig_spread')}bps, HY={result.get('hy_spread')}bps")
            return result

        except Exception as e:
            self._print(f"    [ERR] Credit spreads: {e}")
            return {'error': str(e)}

    # =========================================================================
    # 8. STYLE BOX: GROWTH vs VALUE (yfinance)
    # =========================================================================

    def collect_style_data(self) -> Dict[str, Any]:
        """
        Retornos Growth vs Value via ETFs estándar.

        Datos: Retornos IWF (Growth) vs IWD (Value), spread,
        Large vs Small (IWB vs IWM).

        Fuente: yfinance
        """
        self._print("  -> Style data (Growth/Value/Size)...")

        try:
            import yfinance as yf

            style_etfs = {
                'growth': 'IWF',    # Russell 1000 Growth
                'value': 'IWD',     # Russell 1000 Value
                'large_cap': 'IWB', # Russell 1000
                'small_cap': 'IWM', # Russell 2000
            }

            result = {}

            for style, ticker in style_etfs.items():
                try:
                    hist = yf.Ticker(ticker).history(period='1y')
                    if hist.empty:
                        continue
                    current = hist['Close'].iloc[-1]
                    returns = {}
                    if len(hist) >= 22:
                        returns['1m'] = round(((current / hist['Close'].iloc[-22]) - 1) * 100, 2)
                    if len(hist) >= 63:
                        returns['3m'] = round(((current / hist['Close'].iloc[-63]) - 1) * 100, 2)

                    ytd_cutoff = pd.Timestamp(f'{datetime.now().year}-01-01').tz_localize(hist.index.tz)
                    ytd_start = hist.loc[hist.index >= ytd_cutoff]
                    if not ytd_start.empty:
                        returns['ytd'] = round(((current / ytd_start['Close'].iloc[0]) - 1) * 100, 2)

                    result[style] = {'ticker': ticker, 'returns': returns}
                except Exception as e:
                    result[style] = {'error': str(e)}

            # Calcular spreads si tenemos ambos
            if 'growth' in result and 'value' in result and 'error' not in result['growth'] and 'error' not in result['value']:
                g = result['growth']['returns']
                v = result['value']['returns']
                result['growth_value_spread'] = {
                    period: round(g.get(period, 0) - v.get(period, 0), 2)
                    for period in ['1m', '3m', 'ytd'] if period in g and period in v
                }
                # Señal
                ytd_spread = result['growth_value_spread'].get('ytd', 0)
                result['style_signal'] = 'GROWTH' if ytd_spread > 3 else ('VALUE' if ytd_spread < -3 else 'BALANCED')

            if 'large_cap' in result and 'small_cap' in result and 'error' not in result['large_cap'] and 'error' not in result['small_cap']:
                l = result['large_cap']['returns']
                s = result['small_cap']['returns']
                result['size_spread'] = {
                    period: round(s.get(period, 0) - l.get(period, 0), 2)
                    for period in ['1m', '3m', 'ytd'] if period in l and period in s
                }
                result['size_signal'] = 'SMALL_CAP' if result['size_spread'].get('ytd', 0) > 3 else 'LARGE_CAP'

            result['source'] = 'yfinance'
            self._print(f"    [OK] Style: {result.get('style_signal', 'N/A')}, Size: {result.get('size_signal', 'N/A')}")
            return result

        except Exception as e:
            self._print(f"    [ERR] Style: {e}")
            return {'error': str(e)}

    # =========================================================================
    # 9. DIARIO FINANCIERO INTELLIGENCE
    # =========================================================================

    def collect_df_intelligence(self, days: int = 7) -> Dict[str, Any]:
        """
        Lee los resúmenes del Diario Financiero más recientes.

        Extrae: temas de mercado local, IPSA mentions, TPM,
        noticias corporativas Chile.

        Fuente: df_data/resumen_df_*.txt (Claude Vision summaries)
        """
        self._print(f"  -> Diario Financiero (últimos {days} días)...")

        df_path = Path(os.environ.get('DF_DATA_PATH', str(Path.home() / "OneDrive/Documentos/df/df_data")))

        if not df_path.exists():
            return {'error': f'DF path not found: {df_path}'}

        try:
            # Encontrar archivos recientes
            files = sorted(df_path.glob("resumen_df_*.txt"), reverse=True)

            if not files:
                return {'error': 'No DF summaries found'}

            # Tomar los últimos N días
            recent_files = files[:days]

            summaries = []
            for f in recent_files:
                try:
                    text = f.read_text(encoding='utf-8')
                    summaries.append({
                        'file': f.name,
                        'date': f.name.replace('resumen_df_', '').replace('.txt', '')[:8],
                        'content': text,
                        'length': len(text),
                    })
                except Exception as e:
                    continue

            # Extraer keywords de mercado chileno
            all_text = ' '.join(s['content'] for s in summaries)

            keywords = {
                'ipsa_mentions': all_text.lower().count('ipsa'),
                'tpm_mentions': all_text.lower().count('tpm'),
                'dolar_mentions': all_text.lower().count('dólar') + all_text.lower().count('dollar'),
                'cobre_mentions': all_text.lower().count('cobre'),
                'sqm_mentions': all_text.lower().count('sqm'),
                'banco_central_mentions': all_text.lower().count('banco central'),
            }

            result = {
                'files_found': len(files),
                'files_read': len(summaries),
                'period': f'{summaries[-1]["date"]} to {summaries[0]["date"]}' if len(summaries) > 1 else summaries[0]['date'] if summaries else 'N/A',
                'total_chars': sum(s['length'] for s in summaries),
                'keywords': keywords,
                'latest_summary': summaries[0]['content'][:2000] if summaries else '',
                'source': 'df_data (Claude Vision summaries)',
            }

            self._print(f"    [OK] {len(summaries)} resúmenes DF, IPSA mentions: {keywords['ipsa_mentions']}")
            return result

        except Exception as e:
            self._print(f"    [ERR] DF: {e}")
            return {'error': str(e)}

    # =========================================================================
    # ORQUESTADOR PRINCIPAL
    # =========================================================================

    def collect_all(self) -> Dict[str, Any]:
        """
        Ejecuta todos los módulos y retorna datos consolidados.

        Patrón: cada módulo falla silenciosamente con {'error': str(e)}.
        El content generator debe verificar errores antes de usar datos.

        Returns:
            Dict con keys: valuations, sectors, risk, earnings, factors,
            real_rates, credit, style, df_intelligence, bcch_indices, metadata
        """
        self._print("\n" + "=" * 60)
        self._print("EQUITY DATA COLLECTOR - RECOPILACIÓN DE DATOS")
        self._print("=" * 60)

        start = datetime.now()
        data = {}

        # 1. Valuaciones regionales
        try:
            data['valuations'] = self.collect_regional_valuations()
        except Exception as e:
            data['valuations'] = {'error': str(e)}

        # 2. Datos sectoriales + breadth
        try:
            data['sectors'] = self.collect_sector_data()
        except Exception as e:
            data['sectors'] = {'error': str(e)}

        # 3. Correlaciones y riesgo
        try:
            data['risk'] = self.collect_risk_correlations()
        except Exception as e:
            data['risk'] = {'error': str(e)}

        # 4. Earnings
        try:
            data['earnings'] = self.collect_earnings_data()
        except Exception as e:
            data['earnings'] = {'error': str(e)}

        # 5. Factor analysis
        try:
            data['factors'] = self.collect_factor_data()
        except Exception as e:
            data['factors'] = {'error': str(e)}

        # 6. Real rates + ERP
        try:
            data['real_rates'] = self.collect_real_rates()
        except Exception as e:
            data['real_rates'] = {'error': str(e)}

        # 7. Credit spreads
        try:
            data['credit'] = self.collect_credit_spreads()
        except Exception as e:
            data['credit'] = {'error': str(e)}

        # 8. Style (Growth/Value/Size)
        try:
            data['style'] = self.collect_style_data()
        except Exception as e:
            data['style'] = {'error': str(e)}

        # 9. Diario Financiero
        try:
            data['df_intelligence'] = self.collect_df_intelligence(days=7)
        except Exception as e:
            data['df_intelligence'] = {'error': str(e)}

        # 10. BCCh Indices (IPSA, IGPA, intl indices, USD/CLP, commodities)
        try:
            data['bcch_indices'] = self.collect_bcch_indices()
        except Exception as e:
            data['bcch_indices'] = {'error': str(e)}

        # 11. Chile Top Picks (yfinance ADRs)
        try:
            data['chile_picks'] = self.collect_chile_top_picks()
        except Exception as e:
            data['chile_picks'] = []

        # Metadata
        elapsed = (datetime.now() - start).total_seconds()
        modules_ok = sum(1 for k, v in data.items() if k != 'metadata' and (
            (isinstance(v, dict) and 'error' not in v) or (isinstance(v, list) and len(v) > 0)))
        modules_err = sum(1 for k, v in data.items() if k != 'metadata' and (
            (isinstance(v, dict) and 'error' in v) or (isinstance(v, list) and len(v) == 0)))

        data['metadata'] = {
            'timestamp': datetime.now().isoformat(),
            'elapsed_seconds': round(elapsed, 1),
            'modules_ok': modules_ok,
            'modules_error': modules_err,
            'modules_total': modules_ok + modules_err,
        }

        self._print(f"\n{'=' * 60}")
        self._print(f"COMPLETADO: {modules_ok}/{modules_ok + modules_err} módulos OK "
                    f"({elapsed:.1f}s)")
        self._print(f"{'=' * 60}\n")

        return data

    # =========================================================================
    # 10. ÍNDICES BCCh (BCCh API)
    # =========================================================================

    def collect_bcch_indices(self) -> Dict[str, Any]:
        """
        Obtiene índices bursátiles, tipo de cambio y commodities desde BCCh API.

        Datos: IPSA, IGPA, índices internacionales, USD/CLP, cobre, oro.
        Retornos calculados: 1M, 3M, YTD.

        Fuente: BCCh REST API (si3.bcentral.cl)
        """
        self._print("  [10/10] Índices BCCh (BCCh API)...")

        try:
            from greybark.data_sources.bcch_client import BCChClient
            client = BCChClient()
        except Exception as e:
            return {'error': f'BCChClient not available: {e}'}

        result = {}

        def _fetch_with_returns(code, days=365):
            """Fetch latest value and calculate returns from BCCh series."""
            try:
                data = client.get_series(code, days_back=days)
                if data is None or len(data.dropna()) < 2:
                    return None
                clean = data.dropna()
                latest = float(clean.iloc[-1])
                as_of = str(clean.index[-1].date())

                returns = {}
                if len(clean) >= 22:
                    prev_1m = float(clean.iloc[-22])
                    if prev_1m > 0:
                        returns['1m'] = round(((latest / prev_1m) - 1) * 100, 2)
                if len(clean) >= 63:
                    prev_3m = float(clean.iloc[-63])
                    if prev_3m > 0:
                        returns['3m'] = round(((latest / prev_3m) - 1) * 100, 2)
                if len(clean) >= 252:
                    prev_1y = float(clean.iloc[-252])
                    if prev_1y > 0:
                        returns['1y'] = round(((latest / prev_1y) - 1) * 100, 2)

                # YTD
                year_start = clean.loc[clean.index >= f'{datetime.now().year}-01-01']
                if len(year_start) > 0:
                    first = float(year_start.iloc[0])
                    if first > 0:
                        returns['ytd'] = round(((latest / first) - 1) * 100, 2)

                return {
                    'value': round(latest, 2),
                    'returns': returns,
                    'as_of': as_of,
                }
            except Exception:
                return None

        # --- Chile Indices ---
        ipsa = _fetch_with_returns('F013.IBC.IND.N.7.LAC.CL.CLP.BLO.D')
        if ipsa:
            result['ipsa'] = ipsa
            self._print(f"    [OK] IPSA: {ipsa['value']:,.0f} (YTD: {ipsa['returns'].get('ytd', 'N/A')}%)")

        igpa = _fetch_with_returns('F013.IBG.IND.N.7.LAC.CL.CLP.BLO.D')
        if igpa:
            result['igpa'] = igpa

        # --- International Indices ---
        intl_indices = {
            'sp500': ('F019.IBC.IND.51.D', 'S&P 500'),
            'dow_jones': ('F019.IBC.IND.50.D', 'Dow Jones'),
            'eurostoxx': ('F019.IBC.IND.ZE.D', 'Euro Stoxx 50'),
            'nikkei': ('F019.IBC.IND.52.D', 'Nikkei 225'),
            'csi300': ('F019.IBC.IND.CHN.D', 'CSI 300'),
        }
        for key, (code, name) in intl_indices.items():
            val = _fetch_with_returns(code)
            if val:
                val['name'] = name
                result[key] = val

        # --- USD/CLP ---
        usdclp = _fetch_with_returns('F073.TCO.PRE.Z.D')
        if usdclp:
            result['usd_clp'] = usdclp
            self._print(f"    [OK] USD/CLP: {usdclp['value']:,.0f} (1M: {usdclp['returns'].get('1m', 'N/A')}%)")

        # --- Commodities ---
        commodities = {
            'copper': ('F019.PPB.PRE.100.D', 'Cobre (USc/lb)'),
            'gold': ('F019.PPB.PRE.44.D', 'Oro (USD/oz)'),
            'oil_wti': ('F019.PPB.PRE.41B.D', 'WTI (USD/bbl)'),
            'lithium': ('F019.PPB.PRE.37.D', 'Litio (USD/kg)'),
        }
        for key, (code, name) in commodities.items():
            val = _fetch_with_returns(code)
            if val:
                val['name'] = name
                result[key] = val

        if result:
            self._print(f"    [OK] BCCh: {len(result)} series obtenidas")
        else:
            return {'error': 'No BCCh series returned data'}

        result['source'] = 'BCCh API (si3.bcentral.cl)'
        return result

    # =========================================================================
    # 11. CHILE TOP PICKS (ADRs + Santiago Exchange)
    # =========================================================================

    # ADR tickers (US-listed)
    CHILE_ADR_MAP = {
        'BCH': 'Banco de Chile',
        'BSAC': 'Santander Chile',
        'SQM': 'SQM',
        'LTM': 'LATAM Airlines',
        'CCU': 'CCU',
    }

    # Santiago Exchange tickers (.SN suffix) — IPSA constituents
    CHILE_SN_MAP = {
        'CENCOSUD.SN': ('Cencosud', 'Retail'),
        'FALABELLA.SN': ('Falabella', 'Retail'),
        'COPEC.SN': ('Copec', 'Industrial'),
        'BCI.SN': ('BCI', 'Banca'),
        'ENELCHILE.SN': ('Enel Chile', 'Utilities'),
        'ENELAM.SN': ('Enel Américas', 'Utilities'),
        'CMPC.SN': ('CMPC', 'Forestal'),
        'VAPORES.SN': ('Vapores', 'Naviera'),
        'COLBUN.SN': ('Colbún', 'Utilities'),
        'ITAUCORP.SN': ('Itaú Corpbanca', 'Banca'),
        'CAP.SN': ('CAP', 'Minería'),
        'RIPLEY.SN': ('Ripley', 'Retail'),
        'PARAUCO.SN': ('Parque Arauco', 'Inmobiliario'),
        'SECURITY.SN': ('Security', 'Financiero'),
        'SONDA.SN': ('Sonda', 'Tecnología'),
        'AGUAS-A.SN': ('Aguas Andinas', 'Utilities'),
    }

    def collect_chile_top_picks(self) -> List[Dict[str, Any]]:
        """
        Obtiene datos fundamentales de acciones chilenas via yfinance.

        Fuentes: ADRs (US-listed) + Santiago Exchange (.SN tickers).
        Datos: P/E trailing, P/E forward, dividend yield, precio, 52w high, sector.

        Fuente: yfinance (Yahoo Finance API)
        """
        self._print("  [11/11] Chile top picks (ADRs + Santiago Exchange)...")

        try:
            import yfinance as yf
        except ImportError:
            return []

        picks = []

        # ADRs
        for ticker, name in self.CHILE_ADR_MAP.items():
            try:
                info = yf.Ticker(ticker).info
                pe_trailing = self._safe_float(info.get('trailingPE'))
                pe_forward = self._safe_float(info.get('forwardPE'))
                div_yield_raw = self._safe_float(info.get('dividendYield'))
                if div_yield_raw is not None:
                    # yfinance returns decimal (0.0452) for most tickers; sanity check
                    div_yield = round(div_yield_raw * 100, 2) if div_yield_raw < 1 else round(div_yield_raw, 2)
                else:
                    div_yield = None
                price = self._safe_float(info.get('currentPrice') or info.get('regularMarketPrice'))
                high_52w = self._safe_float(info.get('fiftyTwoWeekHigh'))

                pick = {
                    'ticker': ticker,
                    'name': name,
                    'price': price,
                    'pe_trailing': pe_trailing,
                    'pe_forward': pe_forward,
                    'dividend_yield': div_yield,
                    'fifty_two_week_high': high_52w,
                    'source': 'yfinance',
                }

                # Filter out distorted PE (>80x)
                pe_display = pe_trailing or pe_forward
                if pe_display and pe_display > 80:
                    pick['pe_trailing'] = None
                    pick['pe_forward'] = pe_forward if pe_forward and pe_forward < 80 else None

                self._print(f"    [OK] {ticker} ({name}): PE={pe_trailing}, Div={div_yield}%")
                picks.append(pick)

            except Exception as e:
                self._print(f"    [ERR] {ticker}: {e}")

        adr_count = len(picks)

        # Santiago Exchange (.SN) tickers
        for ticker, (name, sector) in self.CHILE_SN_MAP.items():
            try:
                info = yf.Ticker(ticker).info
                pe_trailing = self._safe_float(info.get('trailingPE'))
                pe_forward = self._safe_float(info.get('forwardPE'))
                div_yield_raw = self._safe_float(info.get('dividendYield'))
                if div_yield_raw is not None:
                    div_yield = round(div_yield_raw * 100, 2) if div_yield_raw < 1 else round(div_yield_raw, 2)
                else:
                    div_yield = None
                price = self._safe_float(info.get('currentPrice') or info.get('regularMarketPrice'))
                high_52w = self._safe_float(info.get('fiftyTwoWeekHigh'))

                pick = {
                    'ticker': ticker.replace('.SN', ''),
                    'name': name,
                    'sector': sector,
                    'price': price,
                    'pe_trailing': pe_trailing,
                    'pe_forward': pe_forward,
                    'dividend_yield': div_yield,
                    'fifty_two_week_high': high_52w,
                    'source': 'yfinance_sn',
                }

                # Filter distorted P/E (>80x) or P/B (>100x)
                pe_display = pe_trailing or pe_forward
                if pe_display and pe_display > 80:
                    pick['pe_trailing'] = None
                    pick['pe_forward'] = pe_forward if pe_forward and pe_forward < 80 else None

                self._print(f"    [OK] {ticker} ({name}): PE={pe_trailing}, Div={div_yield}%, Sector={sector}")
                picks.append(pick)

            except Exception as e:
                self._print(f"    [ERR] {ticker}: {e}")

        sn_count = len(picks) - adr_count
        self._print(f"    [OK] Chile picks: {adr_count} ADRs + {sn_count} Santiago = {len(picks)} total")
        return picks

    def save(self, data: Dict, filepath: str = None) -> str:
        """Guarda datos en JSON."""
        if filepath is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_dir = Path(__file__).parent / 'output' / 'equity_data'
            output_dir.mkdir(parents=True, exist_ok=True)
            filepath = str(output_dir / f'equity_data_{timestamp}.json')

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

        self._print(f"[EquityData] Guardado en: {filepath}")
        return filepath


def main():
    """Ejecuta la recopilación completa de datos equity."""
    print("=" * 60)
    print("GREYBARK RESEARCH - EQUITY DATA COLLECTOR")
    print("=" * 60)

    collector = EquityDataCollector(verbose=True)
    data = collector.collect_all()

    # Guardar
    filepath = collector.save(data)
    print(f"\nDatos guardados en: {filepath}")

    # Resumen
    print("\n--- RESUMEN ---")
    for key, value in data.items():
        if key == 'metadata':
            continue
        if isinstance(value, dict) and 'error' in value:
            print(f"  [ERR] {key}: ERROR - {value['error'][:80]}")
        else:
            print(f"  [OK] {key}: OK")

    return data


if __name__ == "__main__":
    main()
