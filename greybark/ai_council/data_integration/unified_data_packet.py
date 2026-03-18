"""
Greybark Research - Unified Data Packet Builder
================================================

Construye el Data Packet unificado para el AI Council.
Integra TODOS los módulos existentes de greybark.analytics.

Equivalente al TealBook del FOMC en el paper "FOMC In Silico".

Uso:
    from greybark.ai_council.data_integration import UnifiedDataPacketBuilder
    
    builder = UnifiedDataPacketBuilder()
    packet = builder.build_packet()
    builder.save_packet('data_packet.json')
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional
import warnings

# Importar módulos de greybark (con fallbacks si no están disponibles)
try:
    from greybark.analytics.regime_classification import classify_regime
    HAS_REGIME = True
except ImportError:
    HAS_REGIME = False
    warnings.warn("regime_classification not available")

try:
    from greybark.analytics.macro import InflationAnalytics
    HAS_MACRO = True
except ImportError:
    HAS_MACRO = False

try:
    from greybark.analytics.risk import RiskMetrics
    HAS_RISK = True
except ImportError:
    HAS_RISK = False

try:
    from greybark.analytics.credit import CreditSpreadAnalytics
    HAS_CREDIT = True
except ImportError:
    HAS_CREDIT = False

try:
    from greybark.analytics.chile import ChileAnalytics
    HAS_CHILE = True
except ImportError:
    HAS_CHILE = False

try:
    from greybark.analytics.china import ChinaCreditAnalytics
    HAS_CHINA = True
except ImportError:
    HAS_CHINA = False

try:
    from greybark.analytics.breadth import MarketBreadthAnalytics
    HAS_BREADTH = True
except ImportError:
    HAS_BREADTH = False

try:
    from greybark.analytics.factors import FactorAnalytics
    HAS_FACTORS = True
except ImportError:
    HAS_FACTORS = False

try:
    from greybark.analytics.earnings import EarningsAnalytics
    HAS_EARNINGS = True
except ImportError:
    HAS_EARNINGS = False

try:
    from greybark.analytics.fixed_income import DurationAnalytics
    HAS_DURATION = True
except ImportError:
    HAS_DURATION = False

try:
    from greybark.analytics.rate_expectations import USDRateExpectations, CLPRateExpectations
    HAS_RATE_EXP = True
except ImportError:
    HAS_RATE_EXP = False

try:
    from greybark.data_sources import FREDClient, BCChClient, AlphaVantageClient
    HAS_DATA_SOURCES = True
except ImportError:
    HAS_DATA_SOURCES = False


class UnifiedDataPacketBuilder:
    """
    Construye el Data Packet unificado para el AI Council.
    Integra todos los módulos de analytics disponibles.
    """
    
    def __init__(self, verbose: bool = True):
        """
        Inicializa el builder.
        
        Args:
            verbose: Si True, imprime progreso
        """
        self.verbose = verbose
        self._init_modules()
    
    def _init_modules(self):
        """Inicializa los módulos disponibles."""
        self.modules_available = {
            'regime': HAS_REGIME,
            'macro': HAS_MACRO,
            'risk': HAS_RISK,
            'credit': HAS_CREDIT,
            'chile': HAS_CHILE,
            'china': HAS_CHINA,
            'breadth': HAS_BREADTH,
            'factors': HAS_FACTORS,
            'earnings': HAS_EARNINGS,
            'duration': HAS_DURATION,
            'rate_expectations': HAS_RATE_EXP,
            'data_sources': HAS_DATA_SOURCES
        }
        
        if self.verbose:
            available = [k for k, v in self.modules_available.items() if v]
            missing = [k for k, v in self.modules_available.items() if not v]
            print(f"Modules available: {', '.join(available)}")
            if missing:
                print(f"Modules missing: {', '.join(missing)}")
    
    def build_packet(self) -> Dict[str, Any]:
        """
        Construye el paquete completo de datos para el AI Council.
        
        Returns:
            Dict con todas las secciones del data packet
        """
        if self.verbose:
            print("=" * 70)
            print("BUILDING UNIFIED DATA PACKET FOR AI COUNCIL")
            print("=" * 70)
        
        packet = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
                'source': 'greybark.ai_council',
                'modules_used': [k for k, v in self.modules_available.items() if v]
            }
        }
        
        # Construir cada sección
        sections = [
            ('regime_classification', self._get_regime_data),
            ('macro_usa', self._get_macro_usa),
            ('macro_chile', self._get_macro_chile),
            ('equity', self._get_equity_data),
            ('fixed_income', self._get_fixed_income_data),
            ('risk', self._get_risk_data),
            ('credit', self._get_credit_data),
            ('china', self._get_china_data),
            ('news_sentiment', self._get_news_sentiment),
            ('institutional_research', self._get_research_digest),
            ('prediction_markets', self._get_polymarket_data)
        ]
        
        for section_name, section_func in sections:
            if self.verbose:
                print(f"  -> Building {section_name}...")
            try:
                packet[section_name] = section_func()
            except Exception as e:
                packet[section_name] = {'error': str(e), 'status': 'failed'}
                if self.verbose:
                    print(f"    WARNING: Error: {e}")
        
        if self.verbose:
            print("=" * 70)
            print("DATA PACKET COMPLETE")
            print("=" * 70)
        
        return packet
    
    def _get_regime_data(self) -> Dict:
        """
        Obtiene datos de clasificación de régimen.
        Esta es la pieza central del sistema Grey Bark.
        """
        if not HAS_REGIME:
            return {'error': 'regime_classification module not available'}
        
        try:
            result = classify_regime()
            return {
                'classification': result.get('classification', 'UNKNOWN'),
                'score': result.get('score', 0),
                'probabilities': result.get('probabilities', {}),
                'description': result.get('description', ''),
                'asset_allocation_hint': result.get('asset_allocation', {}),
                'top_concerns': result.get('top_concerns', []),
                'top_supports': result.get('top_supports', []),
                'category_scores': result.get('category_scores', {})
            }
        except Exception as e:
            return {'error': str(e), 'classification': 'UNKNOWN'}
    
    def _get_macro_usa(self) -> Dict:
        """Obtiene indicadores macro de USA."""
        data = {}
        
        # Intentar obtener datos de FRED
        if HAS_DATA_SOURCES:
            try:
                fred = FREDClient()
                data['fed_funds'] = fred.get_latest('DFF')
                data['treasury_2y'] = fred.get_latest('DGS2')
                data['treasury_10y'] = fred.get_latest('DGS10')
                data['core_cpi'] = fred.get_latest('CPILFESL')
                data['unemployment'] = fred.get_latest('UNRATE')
                data['ism_manufacturing'] = fred.get_latest('MANEMP')
            except Exception as e:
                data['fred_error'] = str(e)
        
        # Intentar obtener analytics de inflación
        if HAS_MACRO:
            try:
                inflation = InflationAnalytics()
                data['inflation_analytics'] = inflation.get_us_inflation_dashboard()
            except Exception as e:
                data['inflation_error'] = str(e)
        
        # Intentar obtener expectativas de tasas
        if HAS_RATE_EXP:
            try:
                usd_rates = USDRateExpectations()
                data['fed_expectations'] = usd_rates.get_fed_expectations()
            except Exception as e:
                data['rate_exp_error'] = str(e)
        
        return data
    
    def _get_macro_chile(self) -> Dict:
        """
        Obtiene datos macro de Chile.
        DIFERENCIADOR: Chile Profundo
        """
        data = {}
        
        if HAS_CHILE:
            try:
                chile = ChileAnalytics()
                dashboard = chile.get_chile_dashboard()
                data.update(dashboard)
            except Exception as e:
                data['chile_error'] = str(e)
        
        if HAS_RATE_EXP:
            try:
                clp_rates = CLPRateExpectations()
                data['tpm_expectations'] = clp_rates.get_tpm_expectations()
            except Exception as e:
                data['tpm_exp_error'] = str(e)
        
        if HAS_DATA_SOURCES:
            try:
                bcch = BCChClient()
                # Series básicas
                data['tpm_current'] = bcch.get_latest('F074.TPM.PLG.N.D')
                data['usd_clp'] = bcch.get_latest('F073.TCO.PRE.Z.D')
                data['uf'] = bcch.get_latest('F073.UFF.PRE.Z.D')
            except Exception as e:
                data['bcch_error'] = str(e)
        
        return data
    
    def _get_equity_data(self) -> Dict:
        """Obtiene datos de renta variable."""
        data = {}
        
        if HAS_EARNINGS:
            try:
                earnings = EarningsAnalytics()
                data['earnings'] = earnings.get_market_earnings_summary()
            except Exception as e:
                data['earnings_error'] = str(e)
        
        if HAS_FACTORS:
            try:
                factors = FactorAnalytics()
                data['factors'] = factors.get_factor_summary()
            except Exception as e:
                data['factors_error'] = str(e)
        
        if HAS_BREADTH:
            try:
                breadth = MarketBreadthAnalytics()
                data['breadth'] = breadth.get_breadth_summary()
            except Exception as e:
                data['breadth_error'] = str(e)
        
        # Valuaciones básicas desde Yahoo Finance
        try:
            import yfinance as yf
            spy = yf.Ticker('SPY')
            data['sp500_pe'] = spy.info.get('trailingPE')
            data['sp500_forward_pe'] = spy.info.get('forwardPE')
        except Exception as e:
            data['yfinance_error'] = str(e)
        
        return data
    
    def _get_fixed_income_data(self) -> Dict:
        """Obtiene datos de renta fija."""
        data = {}
        
        if HAS_DURATION:
            try:
                duration = DurationAnalytics()
                data['duration_recommendation'] = duration.get_duration_recommendation()
            except Exception as e:
                data['duration_error'] = str(e)
        
        if HAS_DATA_SOURCES:
            try:
                fred = FREDClient()
                data['yields'] = {
                    'treasury_2y': fred.get_latest('DGS2'),
                    'treasury_5y': fred.get_latest('DGS5'),
                    'treasury_10y': fred.get_latest('DGS10'),
                    'treasury_30y': fred.get_latest('DGS30'),
                    'tips_5y': fred.get_latest('DFII5'),
                    'tips_10y': fred.get_latest('DFII10')
                }
                # Calcular curve spread
                if data['yields']['treasury_2y'] and data['yields']['treasury_10y']:
                    data['curve_2s10s'] = data['yields']['treasury_10y'] - data['yields']['treasury_2y']
            except Exception as e:
                data['yields_error'] = str(e)
        
        return data
    
    def _get_risk_data(self) -> Dict:
        """Obtiene métricas de riesgo."""
        data = {}
        
        if HAS_RISK:
            try:
                risk = RiskMetrics()
                data['var'] = risk.calculate_portfolio_var()
                data['stress_tests'] = risk.run_stress_tests()
            except Exception as e:
                data['risk_error'] = str(e)
        
        if HAS_DATA_SOURCES:
            try:
                fred = FREDClient()
                data['vix'] = fred.get_latest('VIXCLS')
            except Exception as e:
                data['vix_error'] = str(e)
        
        return data
    
    def _get_credit_data(self) -> Dict:
        """Obtiene datos de spreads de crédito."""
        data = {}
        
        if HAS_CREDIT:
            try:
                credit = CreditSpreadAnalytics()
                data['ig_spreads'] = credit.get_ig_breakdown()
            except Exception as e:
                data['credit_error'] = str(e)
        
        if HAS_DATA_SOURCES:
            try:
                fred = FREDClient()
                data['spreads'] = {
                    'ig_total': fred.get_latest('BAMLC0A0CM'),
                    'hy_total': fred.get_latest('BAMLH0A0HYM2'),
                    'bbb': fred.get_latest('BAMLC0A4CBBB')
                }
            except Exception as e:
                data['spreads_error'] = str(e)
        
        return data
    
    def _get_china_data(self) -> Dict:
        """
        Obtiene datos de China.
        DIFERENCIADOR: China Credit Impulse
        """
        if not HAS_CHINA:
            return {'error': 'china module not available'}
        
        try:
            china = ChinaCreditAnalytics()
            return china.get_credit_impulse()
        except Exception as e:
            return {'error': str(e)}
    
    def _get_news_sentiment(self) -> Dict:
        """Obtiene sentiment de noticias desde AlphaVantage."""
        if not HAS_DATA_SOURCES:
            return {'error': 'data_sources not available'}
        
        try:
            av = AlphaVantageClient()
            return av.get_market_sentiment()
        except Exception as e:
            return {'error': str(e)}
    
    def _get_research_digest(self) -> Dict:
        """
        Research institucional de Wall Street.
        Usa ResearchCollector para procesar PDFs de research.
        """
        try:
            from .research_collector import ResearchCollector
            import os

            # Buscar carpeta de research
            research_paths = [
                'research',
                'research_pdfs',
                os.path.expanduser('~/Documents/research'),
                os.path.expanduser('~/OneDrive/Documentos/research')
            ]

            research_folder = None
            for path in research_paths:
                if os.path.exists(path) and os.listdir(path):
                    research_folder = path
                    break

            if research_folder is None:
                return {
                    'status': 'no_research_folder',
                    'message': 'Create a folder called "research" with PDF files from Wall Street research',
                    'supported_sources': [
                        'JPMorgan - Guide to the Markets',
                        'Goldman Sachs - Top of Mind',
                        'Bank of America - Fund Manager Survey',
                        'PIMCO - Cyclical Outlook'
                    ],
                    'instructions': 'Place PDF files in ~/Documents/research/ or ./research/'
                }

            # Procesar PDFs
            collector = ResearchCollector(verbose=self.verbose, research_folder=research_folder)
            collector.process_folder()
            return collector.get_research_digest()

        except ImportError:
            return {'error': 'research_collector module not available'}
        except Exception as e:
            return {'error': str(e)}
    
    def _get_polymarket_data(self) -> Dict:
        """
        Datos de Polymarket.
        TODO: Implementar API client
        """
        return {
            'status': 'pending_implementation',
            'description': 'Prediction market odds',
            'planned_markets': [
                'Fed rate decision',
                'US recession probability',
                'Election outcomes',
                'Geopolitical events'
            ]
        }
    
    def save_packet(self, filepath: str = 'data_packet.json') -> Dict:
        """
        Construye y guarda el packet como JSON.
        
        Args:
            filepath: Ruta donde guardar el archivo
            
        Returns:
            El packet construido
        """
        packet = self.build_packet()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(packet, f, indent=2, default=str, ensure_ascii=False)
        
        if self.verbose:
            print(f"\n[OK] Data packet saved to {filepath}")
        
        return packet
    
    def get_packet_summary(self, packet: Optional[Dict] = None) -> str:
        """
        Genera un resumen legible del packet.
        
        Args:
            packet: Packet a resumir. Si None, construye uno nuevo.
            
        Returns:
            String con el resumen
        """
        if packet is None:
            packet = self.build_packet()
        
        lines = [
            "=" * 70,
            "DATA PACKET SUMMARY",
            "=" * 70,
            f"Timestamp: {packet['metadata']['timestamp']}",
            f"Modules used: {', '.join(packet['metadata']['modules_used'])}",
            ""
        ]
        
        # Régimen
        regime = packet.get('regime_classification', {})
        if 'error' not in regime:
            lines.extend([
                "REGIMEN ECONOMICO",
                f"   Classification: {regime.get('classification', 'N/A')}",
                f"   Score: {regime.get('score', 'N/A')}",
                ""
            ])
        
        # Macro USA
        macro_usa = packet.get('macro_usa', {})
        if 'error' not in macro_usa:
            lines.extend([
                "MACRO USA",
                f"   Fed Funds: {macro_usa.get('fed_funds', 'N/A')}",
                f"   Treasury 10Y: {macro_usa.get('treasury_10y', 'N/A')}",
                ""
            ])
        
        # Macro Chile
        macro_chile = packet.get('macro_chile', {})
        if 'error' not in macro_chile:
            lines.extend([
                "MACRO CHILE",
                f"   TPM: {macro_chile.get('tpm_current', 'N/A')}",
                f"   USD/CLP: {macro_chile.get('usd_clp', 'N/A')}",
                ""
            ])
        
        # Risk
        risk = packet.get('risk', {})
        if 'vix' in risk:
            lines.extend([
                "RISK",
                f"   VIX: {risk.get('vix', 'N/A')}",
                ""
            ])
        
        lines.append("=" * 70)
        
        return "\n".join(lines)


# =============================================================================
# STANDALONE EXECUTION
# =============================================================================

if __name__ == "__main__":
    builder = UnifiedDataPacketBuilder(verbose=True)
    packet = builder.save_packet('data_packet.json')
    print(builder.get_packet_summary(packet))
