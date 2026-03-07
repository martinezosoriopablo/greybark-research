# -*- coding: utf-8 -*-
"""
Greybark Research - Council Data Collector
============================================

Recopila TODOS los datos necesarios para ejecutar el AI Council:
1. Datos cuantitativos de los módulos analytics
2. Resumen de reportes diarios del mes
3. Prepara el input consolidado para cada agente

Uso:
    collector = CouncilDataCollector()
    data = collector.prepare_council_input(report_type='macro')
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
import json

# Agregar greybark al path
GREYBARK_PATH = Path(__file__).parent.parent / "02_greybark_library"
sys.path.insert(0, str(GREYBARK_PATH))

from daily_report_parser import DailyReportParser
from daily_intelligence_digest import DailyIntelligenceDigest
from research_analyzer import ResearchAnalyzer
from council_preflight_validator import CouncilPreflightValidator
from bloomberg_reader import BloombergData


INPUT_DIR = Path(__file__).parent / "input"


class CouncilDataCollector:
    """Recopilador de datos para el AI Council."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.daily_parser = DailyReportParser()
        self.intelligence_digest = DailyIntelligenceDigest(business_days=22)
        self.research_analyzer = ResearchAnalyzer(verbose=verbose)
        # Bloomberg data (time series from Excel)
        self.bloomberg = BloombergData()
        # Optional: injected externally by run_monthly.py
        self._equity_data = None
        self._rf_data = None
        self._forecast_data = None

    def _print(self, msg: str):
        if self.verbose:
            print(msg)

    def collect_quantitative_data(self) -> Dict[str, Any]:
        """
        Ejecuta todos los módulos analytics y retorna datos consolidados.

        Returns:
            Dict con datos de cada módulo:
                - regime: clasificación de régimen
                - macro_usa: dashboard macro US
                - macro_chile: dashboard Chile
                - china: credit impulse y EPU
                - inflation: breakevens y real rates
                - rates: expectativas Fed/BCCh
                - risk: VaR y stress test
                - breadth: market breadth
        """
        self._print("[DataCollector] Recopilando datos cuantitativos...")
        data = {}

        # 1. Regime Classification
        try:
            from greybark.analytics.regime_classification import classify_regime
            self._print("  -> Regime classification...")
            regime = classify_regime()
            data['regime'] = {
                'current_regime': regime.get('regime', 'UNKNOWN'),
                'score': regime.get('score', 0),
                'description': regime.get('description', ''),
                'probabilities': regime.get('probabilities', {}),
                'indicators': regime.get('indicator_scores', {})
            }
        except Exception as e:
            self._print(f"  [ERR] Regime: {e}")
            data['regime'] = {'error': str(e)}

        # 2. Macro USA (FRED)
        try:
            from greybark.data_sources.fred_client import FREDClient
            self._print("  -> Macro USA (FRED)...")
            fred = FREDClient()
            macro_usa = fred.get_us_macro_dashboard()
            data['macro_usa'] = macro_usa
        except Exception as e:
            self._print(f"  [ERR] Macro USA: {e}")
            data['macro_usa'] = {'error': str(e)}

        # 2b. Leading Indicators (FRED)
        try:
            self._print("  -> Leading indicators (FRED)...")
            fred_lei = fred if 'fred' in dir() else None
            if fred_lei is None:
                from greybark.data_sources.fred_client import FREDClient
                fred_lei = FREDClient()
            data['leading_indicators'] = fred_lei.get_leading_indicators()
            lei_ok = sum(1 for k, v in data['leading_indicators'].items()
                         if v is not None and k != 'timestamp')
            self._print(f"  [OK] Leading indicators: {lei_ok}/5 series")
        except Exception as e:
            self._print(f"  [ERR] Leading indicators: {e}")
            data['leading_indicators'] = {'error': str(e)}

        # 3. Inflation Analytics
        try:
            from greybark.analytics.macro.inflation_analytics import InflationAnalytics
            self._print("  -> Inflation analytics...")
            inflation = InflationAnalytics()
            be = inflation.get_breakeven_inflation()
            rr = inflation.get_real_rates()
            cpi = inflation.get_cpi_decomposition()
            data['inflation'] = {
                'breakeven_5y': be.get('current', {}).get('breakeven_5y'),
                'breakeven_10y': be.get('current', {}).get('breakeven_10y'),
                'forward_5y5y': be.get('current', {}).get('forward_5y5y'),
                'breakeven_status': be.get('status'),
                'real_rate_10y': rr.get('current', {}).get('tips_10y'),
                'policy_stance': rr.get('policy_stance'),
                'cpi_all_yoy': cpi.get('yoy_percent', {}).get('cpi_all'),
                'cpi_core_yoy': cpi.get('yoy_percent', {}).get('cpi_core'),
                'cpi_services_yoy': cpi.get('yoy_percent', {}).get('cpi_services'),
                'services_status': cpi.get('analysis', {}).get('services', {}).get('status'),
                'interpretation': be.get('interpretation', ''),
            }
        except Exception as e:
            self._print(f"  [ERR] Inflation: {e}")
            data['inflation'] = {'error': str(e)}

        # 4. Chile Analytics
        try:
            from greybark.analytics.chile.chile_analytics import ChileAnalytics
            self._print("  -> Chile analytics...")
            chile = ChileAnalytics()
            snapshot = chile.get_macro_snapshot()
            data['chile'] = snapshot
        except Exception as e:
            self._print(f"  [ERR] Chile: {e}")
            data['chile'] = {'error': str(e)}

        # 5. Chile Extended (BCCh)
        try:
            from greybark.data_sources.bcch_extended import BCChExtendedClient
            self._print("  -> Chile extended (BCCh)...")
            bcch = BCChExtendedClient()
            data['chile_extended'] = {
                'macro': bcch.get_chile_macro(),
                'spc_curve': bcch.get_spc_curve(),
                'credit': bcch.get_credit(),
                'commodities': bcch.get_commodities(),
                'eee_expectations': bcch.get_eee_expectations(),
                'eof_expectations': bcch.get_eof_expectations(),
                'imce': bcch.get_imce(),
                'ipc_detail': bcch.get_ipc_detail(),
            }
        except Exception as e:
            self._print(f"  [ERR] Chile Extended: {e}")
            data['chile_extended'] = {'error': str(e)}

        # 6. China Credit
        try:
            from greybark.analytics.china.china_credit import ChinaCreditAnalytics
            self._print("  -> China credit impulse...")
            china = ChinaCreditAnalytics()
            data['china'] = {
                'credit_impulse': china.get_credit_impulse_proxy(),
                'epu_analysis': china.get_china_epu_analysis(),
                'commodity_demand': china.get_commodity_demand_signals()
            }
        except Exception as e:
            self._print(f"  [ERR] China: {e}")
            data['china'] = {'error': str(e)}

        # 7. Rate Expectations
        try:
            from greybark.analytics.rate_expectations.usd_expectations import generate_fed_expectations
            self._print("  -> Rate expectations (Fed)...")
            fed_exp = generate_fed_expectations(current_fed_funds=4.50, num_meetings=6)
            summary = fed_exp.get('summary', {})
            data['rates'] = {
                'fed_expectations': fed_exp,
                'cuts_expected': summary.get('cuts_expected', 0),
                'hikes_expected': summary.get('hikes_expected', 0),
                'terminal_rate': summary.get('terminal_rate', None),
                'direction': summary.get('direction', 'UNKNOWN')
            }
        except Exception as e:
            self._print(f"  [ERR] Rates: {e}")
            data['rates'] = {'error': str(e)}

        # 8. Risk Metrics
        try:
            from greybark.analytics.risk.metrics import generate_risk_dashboard
            self._print("  -> Risk metrics...")
            # Default portfolio for risk analysis
            default_weights = {
                'SPY': 0.40,  # US Equities
                'EEM': 0.15,  # EM Equities
                'TLT': 0.20,  # US Long Bonds
                'GLD': 0.10,  # Gold
                'HYG': 0.15,  # High Yield
            }
            risk_dashboard = generate_risk_dashboard(default_weights, portfolio_value=1000000)
            data['risk'] = {
                'var_95_daily': risk_dashboard['var'].get('var_95_daily'),
                'var_99_daily': risk_dashboard['var'].get('var_99_daily'),
                'es_95': risk_dashboard['var'].get('es_95'),
                'max_drawdown': risk_dashboard['drawdown'].get('max_drawdown'),
                'current_drawdown': risk_dashboard['drawdown'].get('current_drawdown'),
                'diversification_score': risk_dashboard['correlations'].get('diversification_score'),
                'vix': risk_dashboard['liquidity']['vix'],
                'scorecard': risk_dashboard['scorecard'],
            }
            if risk_dashboard.get('data_status'):
                data['risk']['data_status'] = risk_dashboard['data_status']
                self._print(f"  [WARN] Risk: {risk_dashboard['data_status']}")
        except Exception as e:
            self._print(f"  [ERR] Risk: {e}")
            data['risk'] = {'error': str(e)}

        # 9. Market Breadth
        try:
            from greybark.analytics.breadth.market_breadth import MarketBreadthAnalytics
            self._print("  -> Market breadth...")
            breadth = MarketBreadthAnalytics()
            sb = breadth.get_sector_breadth()
            ra = breadth.get_risk_appetite_indicator()
            cd = breadth.get_cyclical_defensive_ratio()
            sf = breadth.get_size_factor_signal()
            data['breadth'] = {
                'pct_above_50ma': sb.get('metrics', {}).get('pct_above_50ma'),
                'breadth_signal': sb.get('metrics', {}).get('breadth_signal'),
                'breadth_interpretation': sb.get('interpretation', ''),
                'risk_appetite_score': ra.get('risk_appetite_score'),
                'risk_appetite_signal': ra.get('signal'),
                'cyclical_defensive_spread': cd.get('spread'),
                'cycle_position': cd.get('cycle_position'),
                'size_factor_signal': sf.get('signal'),
                'size_factor_interpretation': sf.get('interpretation', ''),
            }
        except Exception as e:
            self._print(f"  [ERR] Breadth: {e}")
            data['breadth'] = {'error': str(e)}

        # 10. International Data (BCCh)
        try:
            from greybark.data_sources.bcch_extended import BCChExtendedClient
            self._print("  -> International data...")
            bcch = BCChExtendedClient()
            data['international'] = {
                'inflation': bcch.get_international_inflation(),
                'core_inflation': bcch.get_international_core_inflation(),
                'bonds_10y': bcch.get_international_bonds(),
                'policy_rates': bcch.get_international_policy_rates(),
                'stock_indices': bcch.get_stock_indices(),
                'gdp': bcch.get_international_gdp(),
                'unemployment': bcch.get_international_unemployment(),
                'volatility_epu': bcch.get_volatility(),
            }
        except Exception as e:
            self._print(f"  [ERR] International: {e}")
            data['international'] = {'error': str(e)}

        # 11. Bloomberg Data (Excel time series)
        try:
            if self.bloomberg.available:
                self._print("  -> Bloomberg data (Excel)...")
                data['bloomberg'] = {
                    'pmi': self.bloomberg.get_pmi_latest(),
                    'cds': self.bloomberg.get_cds_data(),
                    'credit_spreads': self.bloomberg.get_sector_spreads(),
                    'sofr_curve': self.bloomberg.get_sofr_curve(),
                    'epfr_flows': self.bloomberg.get_epfr_flows(),
                    'embi': self.bloomberg.get_embi_spreads(),
                    'china_extended': self.bloomberg.get_china_extended(),
                    'valuations_extended': self.bloomberg.get_valuations_extended(),
                    'factor_returns': self.bloomberg.get_factor_returns(),
                    'intl_curves': self.bloomberg.get_intl_curves(),
                    'available_series': len(self.bloomberg.campos),
                }
                self._print(f"  [OK] Bloomberg: {len(self.bloomberg.campos)} series disponibles")
            else:
                data['bloomberg'] = {'available': False}
        except Exception as e:
            self._print(f"  [ERR] Bloomberg: {e}")
            data['bloomberg'] = {'error': str(e)}

        # 12. CPI Components, Fiscal, LatAm (ChartDataProvider)
        try:
            from chart_data_provider import ChartDataProvider
            self._print("  -> CPI components, fiscal, LatAm macro...")
            cdp = ChartDataProvider(lookback_months=36)
            data['cpi_components'] = cdp.get_usa_cpi_components()
            data['fiscal'] = cdp.get_usa_fiscal()
            data['latam_macro'] = cdp.get_latam_macro()
        except Exception as e:
            self._print(f"  [ERR] CPI/Fiscal/LatAm: {e}")
            data['cpi_components'] = {'error': str(e)}
            data['fiscal'] = {'error': str(e)}
            data['latam_macro'] = {'error': str(e)}

        # 13. BEA (Bureau of Economic Analysis)
        try:
            from greybark.data_sources.bea_client import BEAClient
            self._print("  -> BEA (GDP, PCE, profits, fiscal)...")
            bea = BEAClient()
            if bea.api_key:
                data['bea'] = bea.get_full_dashboard()
                ok_count = sum(1 for v in data['bea'].values()
                               if isinstance(v, dict) and '_source' in v)
                self._print(f"  [OK] BEA: {ok_count}/6 modules")
            else:
                data['bea'] = {'available': False}
                self._print("  [SKIP] BEA: no API key")
        except Exception as e:
            self._print(f"  [ERR] BEA: {e}")
            data['bea'] = {'error': str(e)}

        # 14. OECD KEI (CLI, unemployment, CPI, GDP, rates, confidence)
        try:
            from greybark.data_sources.oecd_client import OECDClient
            self._print("  -> OECD KEI (CLI, confidence, macro)...")
            oecd = OECDClient()
            data['oecd'] = {
                'cli': oecd.get_cli(),
                'cci': oecd.get_consumer_confidence(),
                'bci': oecd.get_business_confidence(),
                'unemployment': oecd.get_unemployment(),
                'cpi_inflation': oecd.get_cpi_inflation(),
                'interest_rates': oecd.get_interest_rates(),
            }
            ok_count = sum(1 for v in data['oecd'].values()
                           if isinstance(v, dict) and len(v) > 1)
            self._print(f"  [OK] OECD: {ok_count}/6 series")
        except Exception as e:
            self._print(f"  [ERR] OECD: {e}")
            data['oecd'] = {'error': str(e)}

        # 15. NY Fed (SOFR/EFFR/OBFR, GSCPI, R-star, Term Premia)
        try:
            from greybark.data_sources.nyfed_client import NYFedClient
            self._print("  -> NY Fed (rates, GSCPI, R-star, term premia)...")
            nyfed = NYFedClient()
            data['nyfed'] = nyfed.get_full_dashboard()
            ok_count = sum(1 for v in data['nyfed'].values()
                           if isinstance(v, dict) and len(v) > 1)
            self._print(f"  [OK] NY Fed: {ok_count}/5 modules")
        except Exception as e:
            self._print(f"  [ERR] NY Fed: {e}")
            data['nyfed'] = {'error': str(e)}

        self._print("[DataCollector] Datos cuantitativos completados")
        return data

    def collect_daily_reports_summary(self, days: int = 30) -> Dict[str, Any]:
        """
        Lee los últimos N reportes diarios y genera un resumen.

        Args:
            days: Número de días hacia atrás

        Returns:
            Dict con resumen consolidado
        """
        self._print(f"[DataCollector] Recopilando reportes diarios (últimos {days} días)...")

        summary = self.daily_parser.get_monthly_summary(days=days, report_type="no_finanzas")

        self._print(f"  -> Encontrados: {summary.get('reports_count', 0)} reportes")
        self._print(f"  -> Período: {summary.get('period', 'N/A')}")

        return summary

    def collect_intelligence_digest(self) -> Dict[str, Any]:
        """
        Genera el Daily Intelligence Digest: análisis narrativo profundo
        de los reportes diarios AM/PM.

        Extrae: temas dominantes con contexto, evolución de sentimiento,
        ideas tácticas categorizadas, y narrativas semanales.

        Returns:
            Dict con digest estructurado (themes, sentiment, ideas, etc.)
        """
        self._print("[DataCollector] Generando Intelligence Digest...")

        try:
            digest = self.intelligence_digest.generate()
            meta = digest.get('metadata', {})
            n_themes = len(digest.get('themes', {}))
            n_ideas = len(digest.get('tactical_ideas', []))

            self._print(f"  -> {meta.get('reports_count', 0)} reportes analizados "
                        f"({meta.get('business_days_covered', 0)} días hábiles)")
            self._print(f"  -> {n_themes} temas detectados, {n_ideas} ideas tácticas")

            # Sentimiento dominante de la última semana
            sentiment = digest.get('sentiment_evolution', [])
            if sentiment:
                last = sentiment[-1]
                self._print(f"  -> Sentimiento actual: {last['dominant_tone'].upper()}")

            return digest
        except Exception as e:
            self._print(f"  [ERR] Intelligence Digest: {e}")
            return {'metadata': {'error': str(e)}, 'themes': {}, 'sentiment_evolution': [],
                    'tactical_ideas': [], 'weekly_narratives': [], 'key_events': []}

    def collect_user_directives(self) -> str:
        """
        Lee directivas del usuario desde input/user_directives.txt.

        El usuario edita este archivo antes de correr el consejo con su foco,
        preguntas, restricciones o contexto adicional.

        Returns:
            Texto de directivas (sin comentarios). Vacío si no hay.
        """
        filepath = INPUT_DIR / "user_directives.txt"
        if not filepath.exists():
            self._print("[DataCollector] Sin directivas de usuario (archivo no existe)")
            return ''

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Filtrar comentarios y líneas vacías
            content_lines = [
                line.rstrip() for line in lines
                if line.strip() and not line.strip().startswith('#')
            ]

            text = '\n'.join(content_lines).strip()

            if text:
                self._print(f"[DataCollector] Directivas de usuario: {len(text)} chars")
                self._print(f"  -> Preview: {text[:120]}...")
            else:
                self._print("[DataCollector] Sin directivas de usuario (solo comentarios)")

            return text

        except Exception as e:
            self._print(f"  [ERR] Leyendo directivas: {e}")
            return ''

    def collect_external_research(self) -> str:
        """
        Lee archivos de research externo desde input/research/ y los
        analiza con un LLM para extraer temas, consensos, discrepancias
        e implicancias para el portafolio.

        Si no hay API key disponible, retorna el texto crudo concatenado.

        Returns:
            Síntesis estructurada del research (o texto crudo como fallback).
        """
        return self.research_analyzer.analyze()

    def prepare_council_input(self, report_type: str = 'macro') -> Dict[str, Any]:
        """
        Consolida todo en el formato que necesita el Council.

        Args:
            report_type: 'macro' | 'rv' | 'rf' | 'aa'

        Returns:
            Dict con toda la data estructurada para los agentes
        """
        self._print(f"\n{'='*60}")
        self._print(f"PREPARANDO INPUT PARA AI COUNCIL - {report_type.upper()}")
        self._print(f"{'='*60}\n")

        # Recopilar todo
        quant_data = self.collect_quantitative_data()
        daily_summary = self.collect_daily_reports_summary(days=30)
        intelligence = self.collect_intelligence_digest()
        user_directives = self.collect_user_directives()
        external_research = self.collect_external_research()

        # Usar Intelligence Digest como contexto principal para prompts
        # format_for_council() da ~12K chars con temas, sentimiento, ideas
        daily_context = self.intelligence_digest.format_for_council(intelligence)

        # Preflight validation
        validator = CouncilPreflightValidator(verbose=self.verbose)
        preflight = validator.validate(quant_data, daily_summary, daily_context)
        validator.print_report(preflight)

        # Construir input consolidado
        council_input = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'report_type': report_type,
                'daily_reports_count': daily_summary.get('reports_count', 0),
                'intelligence_themes': len(intelligence.get('themes', {})),
                'intelligence_ideas': len(intelligence.get('tactical_ideas', [])),
                'has_user_directives': bool(user_directives),
                'has_external_research': bool(external_research),
                'has_bloomberg': self.bloomberg.available,
                'bloomberg_series': len(self.bloomberg.campos) if self.bloomberg.available else 0,
            },
            'quantitative': quant_data,
            'daily_context': daily_context,
            'intelligence_briefing': getattr(self, '_intelligence_briefing', ''),
            'wsj_context': getattr(self, '_wsj_context', ''),
            'daily_summary': daily_summary,
            'intelligence': intelligence,
            'user_directives': user_directives,
            'external_research': external_research,
            'preflight': preflight.to_dict()
        }

        # Include equity data if available (injected by run_monthly.py)
        if self._equity_data and isinstance(self._equity_data, dict) and 'error' not in self._equity_data:
            council_input['equity_data'] = self._equity_data
            council_input['metadata']['has_equity_data'] = True
            self._print(f"[DataCollector] Equity data incluida ({self._equity_data.get('metadata', {}).get('modules_ok', '?')} módulos)")

        # Preparar data específica por agente
        council_input['agent_data'] = self._prepare_agent_specific_data(
            quant_data, daily_summary, intelligence, report_type
        )

        # Inject equity data into RV agent if available
        if self._equity_data and isinstance(self._equity_data, dict) and 'error' not in self._equity_data:
            rv_agent = council_input['agent_data'].get('rv', {})
            rv_agent['equity_data'] = {
                'valuations': self._equity_data.get('valuations', {}),
                'real_rates': self._equity_data.get('real_rates', {}),
                'credit': self._equity_data.get('credit', {}),
                'style': self._equity_data.get('style', {}),
                # FIX: data que se recopilaba pero nunca llegaba al RV
                'earnings': self._equity_data.get('earnings', {}),
                'factors': self._equity_data.get('factors', {}),
                'sectors': self._equity_data.get('sectors', {}),
                # NUEVO: AlphaVantage Premium deep-dive
                'market_movers': self._equity_data.get('market_movers', {}),
                'news_sentiment': self._equity_data.get('news_sentiment', {}),
            }
            # Also give riesgo agent the risk metrics
            riesgo_agent = council_input['agent_data'].get('riesgo', {})
            riesgo_agent['equity_risk'] = self._equity_data.get('risk', {})
            riesgo_agent['equity_credit'] = self._equity_data.get('credit', {})

        # Inject RF data into RF agent if available
        if self._rf_data and isinstance(self._rf_data, dict) and 'error' not in self._rf_data:
            council_input['rf_data'] = self._rf_data
            council_input['metadata']['has_rf_data'] = True
            self._print(f"[DataCollector] RF data incluida ({self._rf_data.get('metadata', {}).get('modules_ok', '?')} módulos)")

            rf_agent = council_input['agent_data'].get('rf', {})
            rf_agent['rf_data'] = {
                'yield_curve': self._rf_data.get('yield_curve', {}),
                'duration': self._rf_data.get('duration', {}),
                'credit_spreads': self._rf_data.get('credit_spreads', {}),
                'inflation': self._rf_data.get('inflation', {}),
                'fed_expectations': self._rf_data.get('fed_expectations', {}),
                'tpm_expectations': self._rf_data.get('tpm_expectations', {}),
            }
            # Riesgo agent also benefits from credit + rates data
            riesgo_agent = council_input['agent_data'].get('riesgo', {})
            riesgo_agent['rf_credit'] = self._rf_data.get('credit_spreads', {})
            riesgo_agent['rf_duration'] = self._rf_data.get('duration', {})

        # Inject forecast data if available
        if self._forecast_data and isinstance(self._forecast_data, dict) and 'error' not in self._forecast_data:
            council_input['forecast_data'] = self._forecast_data
            council_input['metadata']['has_forecast_data'] = True
            self._print(f"[DataCollector] Forecast data incluida ({self._forecast_data.get('metadata', {}).get('modules_ok', '?')} módulos)")

            # Macro agent sees GDP + inflation forecasts
            macro_agent = council_input['agent_data'].get('macro', {})
            macro_agent['forecasts'] = {
                'gdp': self._forecast_data.get('gdp_forecasts', {}),
                'inflation': self._forecast_data.get('inflation_forecasts', {}),
                'rates': self._forecast_data.get('rate_forecasts', {}),
            }

            # RV agent sees equity targets
            rv_agent = council_input['agent_data'].get('rv', {})
            rv_agent['equity_targets'] = self._forecast_data.get('equity_targets', {})

            # RF agent sees rate forecasts
            rf_agent = council_input['agent_data'].get('rf', {})
            rf_agent['rate_forecasts'] = self._forecast_data.get('rate_forecasts', {})

            # Riesgo and Geo agents see summary
            for agent_key in ('riesgo', 'geo'):
                agent = council_input['agent_data'].get(agent_key, {})
                agent['forecast_summary'] = {
                    'gdp_usa': self._forecast_data.get('gdp_forecasts', {}).get('usa', {}).get('forecast_12m'),
                    'inflation_usa': self._forecast_data.get('inflation_forecasts', {}).get('usa', {}).get('forecast_12m'),
                    'fed_direction': self._forecast_data.get('rate_forecasts', {}).get('fed_funds', {}).get('direction'),
                }

        # Data completeness validation (field-by-field)
        try:
            from data_completeness_validator import DataCompletenessValidator
            completeness_validator = DataCompletenessValidator(verbose=self.verbose)
            completeness = completeness_validator.validate(council_input['agent_data'])
            council_input['completeness'] = completeness.to_dict()

            # Override preflight verdict if completeness is worse
            if completeness.verdict == 'NO_GO' and council_input['preflight'].get('overall_verdict') != 'NO_GO':
                council_input['preflight']['overall_verdict'] = 'NO_GO'
                self._print("[DataCollector] Completeness override: NO_GO")
        except Exception as e:
            self._print(f"[DataCollector] Completeness validation failed: {e}")
            council_input['completeness'] = {'error': str(e)}

        self._print(f"\n[DataCollector] Input preparado para {report_type}")

        return council_input

    def _prepare_agent_specific_data(
        self,
        quant: Dict,
        daily: Dict,
        intelligence: Dict,
        report_type: str
    ) -> Dict[str, Dict]:
        """Prepara datos filtrados para cada agente según su expertise."""

        themes = intelligence.get('themes', {})
        sentiment = intelligence.get('sentiment_evolution', [])
        ideas = intelligence.get('tactical_ideas', [])

        # Helper: filtrar temas por categorías relevantes para cada agente
        def filter_themes(categories):
            return {
                tid: {
                    'category': t['category'],
                    'report_days': t['report_days'],
                    'trend': t['trend'],
                    'recent_contexts': t['recent_contexts'][:2],
                }
                for tid, t in themes.items()
                if t['category'] in categories
            }

        # Helper: filtrar ideas por asset class
        def filter_ideas(categories):
            return [i for i in ideas[-5:] if i['category'] in categories]

        agent_data = {}

        # IAS Macro: regime + macro + inflation + chile + china + international + BEA + LEI + OECD + NYFed
        chile_ext = quant.get('chile_extended', {})
        bea = quant.get('bea', {})
        oecd = quant.get('oecd', {})
        nyfed = quant.get('nyfed', {})
        bbg = quant.get('bloomberg', {})
        agent_data['macro'] = {
            'regime': quant.get('regime', {}),
            'macro_usa': quant.get('macro_usa', {}),
            'leading_indicators': quant.get('leading_indicators', {}),
            'inflation': quant.get('inflation', {}),
            'cpi_components': quant.get('cpi_components', {}),
            'fiscal': quant.get('fiscal', {}),
            'chile': quant.get('chile', {}),
            'chile_eee': chile_ext.get('eee_expectations', {}),
            'chile_imce': chile_ext.get('imce', {}),
            'chile_ipc_detail': chile_ext.get('ipc_detail', {}),
            'china': quant.get('china', {}),
            'international': quant.get('international', {}),
            'latam_macro': quant.get('latam_macro', {}),
            # BEA data
            'bea_gdp': bea.get('gdp', {}),
            'bea_pce': bea.get('pce_inflation', {}),
            'bea_income': bea.get('personal_income', {}),
            'bea_profits': bea.get('corporate_profits', {}),
            'bea_fiscal': bea.get('fiscal', {}),
            # OECD
            'oecd_cli': oecd.get('cli', {}),
            'oecd_cci': oecd.get('cci', {}),
            'oecd_bci': oecd.get('bci', {}),
            'oecd_unemployment': oecd.get('unemployment', {}),
            'oecd_cpi': oecd.get('cpi_inflation', {}),
            # NY Fed
            'nyfed_rstar': nyfed.get('rstar', {}),
            'nyfed_gscpi': nyfed.get('gscpi', {}),
            'nyfed_term_premia': nyfed.get('term_premia', {}),
            # Bloomberg structured
            'bbg_pmi': bbg.get('pmi', {}),
            'bbg_china_extended': bbg.get('china_extended', {}),
            'bloomberg_context': self.bloomberg.format_for_macro_agent() if self.bloomberg.available else '',
            'intelligence_themes': filter_themes([
                'Política Monetaria', 'Inflación', 'Crecimiento', 'Chile',
            ]),
            'sentiment': sentiment[-2:] if sentiment else [],
            'temas_mes': daily.get('temas_recurrentes', []),
        }

        # IAS RV: regime + breadth + international indices
        agent_data['rv'] = {
            'regime': quant.get('regime', {}),
            'breadth': quant.get('breadth', {}),
            'indices': quant.get('international', {}).get('stock_indices', {}),
            'macro_usa': quant.get('macro_usa', {}),
            # Bloomberg structured
            'bbg_valuations': bbg.get('valuations_extended', {}),
            'bbg_factor_returns': bbg.get('factor_returns', {}),
            'bbg_epfr_flows': bbg.get('epfr_flows', {}),
            'bloomberg_context': self.bloomberg.format_for_rv_agent() if self.bloomberg.available else '',
            'intelligence_themes': filter_themes([
                'Tecnología', 'Earnings', 'Crecimiento', 'LatAm',
            ]),
            'tactical_ideas': filter_ideas(['Renta Variable', 'General']),
            'sentiment': sentiment[-2:] if sentiment else [],
            'temas_mes': daily.get('temas_recurrentes', []),
        }

        # IAS RF: regime + rates + inflation + chile rates + fiscal + NYFed
        agent_data['rf'] = {
            'regime': quant.get('regime', {}),
            'rates': quant.get('rates', {}),
            'inflation': quant.get('inflation', {}),
            'cpi_components': quant.get('cpi_components', {}),
            'fiscal': quant.get('fiscal', {}),
            'chile': quant.get('chile', {}),
            'chile_extended': quant.get('chile_extended', {}),
            'bonds_intl': quant.get('international', {}).get('bonds_10y', {}),
            # NY Fed rates and term premia
            'nyfed_rates': nyfed.get('reference_rates', {}),
            'nyfed_term_premia': nyfed.get('term_premia', {}),
            'nyfed_rstar': nyfed.get('rstar', {}),
            # OECD rates
            'oecd_rates': oecd.get('interest_rates', {}),
            # Bloomberg structured data
            'bbg_sofr_curve': bbg.get('sofr_curve', {}),
            'bbg_credit_spreads': bbg.get('credit_spreads', {}),
            'bbg_cds': bbg.get('cds', {}),
            'bbg_intl_curves': bbg.get('intl_curves', {}),
            'bloomberg_context': self.bloomberg.format_for_rf_agent() if self.bloomberg.available else '',
            'intelligence_themes': filter_themes([
                'Política Monetaria', 'Inflación', 'Renta Fija',
            ]),
            'tactical_ideas': filter_ideas(['Renta Fija']),
            'sentiment': sentiment[-2:] if sentiment else [],
            'temas_mes': daily.get('temas_recurrentes', []),
        }

        # IAS Riesgo: regime + risk + volatility/EPU + GSCPI
        agent_data['riesgo'] = {
            'regime': quant.get('regime', {}),
            'risk': quant.get('risk', {}),
            'china': quant.get('china', {}),
            'volatility_epu': quant.get('international', {}).get('volatility_epu', {}),
            'nyfed_gscpi': nyfed.get('gscpi', {}),
            'oecd_cli': oecd.get('cli', {}),
            # Bloomberg structured: CDS + credit spreads for risk monitoring
            'bbg_cds': bbg.get('cds', {}),
            'bbg_credit_spreads': bbg.get('credit_spreads', {}),
            'bloomberg_context': self.bloomberg.format_for_risk_agent() if self.bloomberg.available else '',
            'intelligence_themes': filter_themes([
                'Riesgo', 'Geopolítica', 'Crecimiento',
            ]),
            'tactical_ideas': filter_ideas(['Cobertura']),
            'sentiment': sentiment,  # Riesgo ve toda la evolución
            'temas_mes': daily.get('temas_recurrentes', []),
        }

        # IAS Geo: contexto geopolítico + commodities + international + EPU + LEI + OECD + GSCPI
        agent_data['geo'] = {
            'daily_context': daily,
            'regime': quant.get('regime', {}),
            'commodities': quant.get('chile_extended', {}).get('commodities', {}),
            'epu': quant.get('china', {}).get('epu_signal', {}),
            'volatility_epu': quant.get('international', {}).get('volatility_epu', {}),
            'leading_indicators': quant.get('leading_indicators', {}),
            'international': quant.get('international', {}),
            'oecd_cli': oecd.get('cli', {}),
            'oecd_cci': oecd.get('cci', {}),
            'nyfed_gscpi': nyfed.get('gscpi', {}),
            # Bloomberg structured: CDS + EMBI for geopolitical stress
            'bbg_cds': bbg.get('cds', {}),
            'bbg_embi': bbg.get('embi', {}),
            'bbg_china_extended': bbg.get('china_extended', {}),
            'bloomberg_context': self.bloomberg.format_for_geo_agent() if self.bloomberg.available else '',
            'intelligence_themes': filter_themes([
                'Geopolítica', 'Commodities', 'LatAm', 'Chile',
            ]),
            'tactical_ideas': filter_ideas(['Commodities', 'Divisas']),
            'sentiment': sentiment[-2:] if sentiment else [],
            'temas_mes': daily.get('temas_recurrentes', []),
        }

        return agent_data

    def save_input(self, council_input: Dict, filepath: str = None) -> str:
        """Guarda el input en JSON."""
        if filepath is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filepath = Path(__file__).parent / 'output' / 'council' / f'council_input_{timestamp}.json'

        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(council_input, f, indent=2, ensure_ascii=False, default=str)

        self._print(f"[DataCollector] Input guardado en: {filepath}")
        return str(filepath)


def main():
    """Test del collector."""
    print("=" * 60)
    print("COUNCIL DATA COLLECTOR - TEST")
    print("=" * 60)

    collector = CouncilDataCollector(verbose=True)

    # Test individual components
    print("\n--- Test: Datos cuantitativos ---")
    quant = collector.collect_quantitative_data()
    print(f"Módulos recopilados: {list(quant.keys())}")

    print("\n--- Test: Reportes diarios ---")
    daily = collector.collect_daily_reports_summary(days=30)
    print(f"Reportes: {daily.get('reports_count', 0)}")

    print("\n--- Test: Input completo ---")
    full_input = collector.prepare_council_input(report_type='macro')
    print(f"Keys: {list(full_input.keys())}")

    # Guardar
    filepath = collector.save_input(full_input)
    print(f"\nGuardado en: {filepath}")


if __name__ == "__main__":
    main()
