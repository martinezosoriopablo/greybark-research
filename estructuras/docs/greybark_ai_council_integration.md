# GREYBARK RESEARCH - AI COUNCIL INTEGRATION
## Fusión del Framework FOMC In Silico con la Arquitectura Existente
### Fecha: 24 Enero 2026

---

## 1. ESTADO ACTUAL vs OBJETIVO

### 1.1 Lo que YA TIENES (Librería `greybark`)

```
greybark/
├── data_sources/              ✅ COMPLETO
│   ├── fred_client.py         # Macro USA, yields, spreads
│   ├── bcch_client.py         # Chile: TPM, IPC, swaps
│   ├── alphavantage_client.py # Fundamentals, earnings, sentiment
│   └── commloan_scraper.py    # SOFR forwards
│
├── analytics/                 ✅ COMPLETO
│   ├── regime_classification/ # 11 indicadores → régimen
│   ├── rate_expectations/     # Fed/TPM expectations
│   ├── risk/                  # VaR, Stress, LSTM
│   ├── macro/                 # Inflation analytics
│   ├── earnings/              # EPS analytics
│   ├── fixed_income/          # Duration
│   ├── chile/                 # Chile Profundo
│   ├── factors/               # Factor analysis
│   ├── china/                 # China credit
│   ├── credit/                # IG/HY spreads
│   └── breadth/               # Market breadth
│
├── tracking/                  ✅ COMPLETO
│   └── track_record.py        # Accountability
│
└── reports/                   🔲 PENDIENTE
    └── __init__.py            # Vacío
```

### 1.2 Lo que FALTA (AI Council)

```
greybark/
├── ai_council/               🆕 NUEVO MÓDULO
│   ├── __init__.py
│   ├── agents/               # Los 6-8 agentes especializados
│   │   ├── base_agent.py
│   │   ├── macro_strategist.py
│   │   ├── equity_analyst.py
│   │   ├── fixed_income_specialist.py
│   │   ├── risk_manager.py
│   │   ├── geopolitics_analyst.py
│   │   └── quant_analyst.py
│   │
│   ├── deliberation/         # Motor de debate (del paper FOMC)
│   │   ├── opinion_formation.py
│   │   ├── cross_critique.py
│   │   ├── consensus_builder.py
│   │   └── voting.py
│   │
│   ├── data_integration/     # Conecta analytics existentes
│   │   ├── unified_data_packet.py
│   │   └── research_collector.py  # Wall Street research
│   │
│   └── output/               # Genera reportes finales
│       ├── report_generator.py
│       └── templates/
│
└── config.py                 # + Claude API key
```

---

## 2. MAPEO: TUS 5 IAS → 6 AGENTES FOMC-STYLE

### Tu Arquitectura Original (MASTER_INDEX.yaml)

```
┌─────────────────────────────────────────────────────────────────────┐
│              CAPA 1: PANEL HORIZONTAL (5 IAS en paralelo)           │
│                                                                     │
│   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────┐  │
│   │IAS MACRO│ │ IAS RV  │ │ IAS RF  │ │IAS RIESG│ │IAS GEOPOLIT.│  │
│   └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └──────┬──────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                   ↓
┌─────────────────────────────────────────────────────────────────────┐
│              CAPA 2: SÍNTESIS VERTICAL (secuencial)                 │
│                                                                     │
│   ┌────────────────┐    ┌────────────────┐    ┌──────────────────┐ │
│   │    IAS CIO     │───▶│ IAS CONTRARIAN │───▶│ REFINADOR FINAL  │ │
│   └────────────────┘    └────────────────┘    └──────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### Nueva Arquitectura Integrada (FOMC-Style)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FASE 1: DATA INPUTS                         │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ greybark.data_sources + greybark.analytics + Research Inst.  │  │
│  │  • regime_classification.json                                │  │
│  │  • macro_indicators (FRED, BCCh)                             │  │
│  │  • market_data (Yahoo, Alpha Vantage)                        │  │
│  │  • news_digest (Occidental + Global + Polymarket)            │  │
│  │  • wall_street_research (JPM, GS, Vanguard, PIMCO...)        │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              ↓                                      │
│              [Unified Data Packet - JSON]                           │
└─────────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│          FASE 2: FORMACIÓN DE OPINIÓN INDIVIDUAL                    │
│                                                                     │
│  Cada agente recibe el Data Packet + su Persona y genera:          │
│  • Recommended allocation                                           │
│  • Conviction score (0-100)                                         │
│  • Key reasoning                                                    │
│  • Risks & opportunities                                            │
│                                                                     │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │
│  │  MACRO  │ │ EQUITY  │ │  FIXED  │ │  RISK   │ │ GEOPOL  │       │
│  │         │ │         │ │ INCOME  │ │ MANAGER │ │         │       │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘       │
│       │          │          │          │          │                │
│  JSON Opinion  JSON Opinion  ...       ...       ...               │
└───────┼──────────┼──────────┼──────────┼──────────┼─────────────────┘
        └──────────┴──────────┴──────────┴──────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│          FASE 3: DELIBERACIÓN MULTI-RONDA (FOMC-Style)              │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ RONDA 1: PRESENTACIONES                                      │   │
│  │ Cada agente presenta su visión al comité                     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                          ↓                                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ RONDA 2: CRÍTICA CRUZADA                                     │   │
│  │ • Macro critica a Equity: "Estás ignorando riesgo recesión"  │   │
│  │ • Risk critica a Fixed Income: "Duration demasiado larga"    │   │
│  │ • Geopolitics critica a todos: "Ignoran riesgo China"        │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                          ↓                                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ RONDA 3: REFINAMIENTO                                        │   │
│  │ Agentes actualizan opiniones basado en críticas              │   │
│  │ (Bayesian updating como en el paper FOMC)                    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                          ↓                                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ RONDA 4: SÍNTESIS CIO (Chief Investment Officer)             │   │
│  │ • Identifica consensos                                       │   │
│  │ • Documenta disensos                                         │   │
│  │ • Propone allocation final                                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                          ↓                                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ RONDA 5: VOTACIÓN FINAL                                      │   │
│  │ • Cada agente vota AGREE/DISAGREE                            │   │
│  │ • Se registran disensos con razón específica                 │   │
│  │ • Conviction promedio del comité                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    OUTPUT: COMMITTEE REPORT                         │
│  • Asset Allocation Final (% por clase)                             │
│  • Conviction Level (0-100)                                         │
│  • Consensos del Comité                                             │
│  • Disensos Documentados (VALOR ÚNICO)                              │
│  • Key Risks to Monitor                                             │
│  • Triggers for Rebalancing                                         │
│  • Track Record Update                                              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. INTEGRACIÓN CON MÓDULOS EXISTENTES

### 3.1 Data Packet Builder (usa tus analytics existentes)

```python
# greybark/ai_council/data_integration/unified_data_packet.py

from greybark.analytics.regime_classification import classify_regime
from greybark.analytics.macro import InflationAnalytics
from greybark.analytics.risk import RiskMetrics
from greybark.analytics.credit import CreditSpreadAnalytics
from greybark.analytics.chile import ChileAnalytics
from greybark.analytics.china import ChinaCreditAnalytics
from greybark.analytics.breadth import MarketBreadthAnalytics
from greybark.analytics.factors import FactorAnalytics
from greybark.analytics.earnings import EarningsAnalytics
from greybark.analytics.fixed_income import DurationAnalytics
from greybark.analytics.rate_expectations import (
    USDRateExpectations, 
    CLPRateExpectations
)
from greybark.data_sources import FREDClient, BCChClient, AlphaVantageClient

import json
from datetime import datetime
from typing import Dict, Any


class UnifiedDataPacketBuilder:
    """
    Construye el Data Packet unificado para el AI Council.
    Integra TODOS los módulos existentes de greybark.analytics.
    """
    
    def __init__(self):
        # Data Sources
        self.fred = FREDClient()
        self.bcch = BCChClient()
        self.av = AlphaVantageClient()
        
        # Analytics modules
        self.inflation = InflationAnalytics()
        self.risk = RiskMetrics()
        self.credit = CreditSpreadAnalytics()
        self.chile = ChileAnalytics()
        self.china = ChinaCreditAnalytics()
        self.breadth = MarketBreadthAnalytics()
        self.factors = FactorAnalytics()
        self.earnings = EarningsAnalytics()
        self.duration = DurationAnalytics()
        self.usd_rates = USDRateExpectations()
        self.clp_rates = CLPRateExpectations()
    
    def build_packet(self) -> Dict[str, Any]:
        """
        Construye el paquete completo de datos para el AI Council.
        Equivalente al TealBook del FOMC.
        """
        
        print("=" * 70)
        print("BUILDING UNIFIED DATA PACKET FOR AI COUNCIL")
        print("=" * 70)
        
        packet = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
                'source': 'greybark.ai_council'
            },
            
            # SECCIÓN 1: RÉGIMEN ECONÓMICO (tu sistema existente)
            'regime_classification': self._get_regime_data(),
            
            # SECCIÓN 2: MACRO USA
            'macro_usa': self._get_macro_usa(),
            
            # SECCIÓN 3: MACRO CHILE
            'macro_chile': self._get_macro_chile(),
            
            # SECCIÓN 4: RENTA VARIABLE
            'equity': self._get_equity_data(),
            
            # SECCIÓN 5: RENTA FIJA
            'fixed_income': self._get_fixed_income_data(),
            
            # SECCIÓN 6: RIESGO
            'risk': self._get_risk_data(),
            
            # SECCIÓN 7: CRÉDITO
            'credit': self._get_credit_data(),
            
            # SECCIÓN 8: CHINA
            'china': self._get_china_data(),
            
            # SECCIÓN 9: NEWS & SENTIMENT (pendiente integración)
            'news_sentiment': self._get_news_sentiment(),
            
            # SECCIÓN 10: RESEARCH INSTITUCIONAL (nuevo)
            'institutional_research': self._get_research_digest(),
            
            # SECCIÓN 11: POLYMARKET (nuevo)
            'prediction_markets': self._get_polymarket_data()
        }
        
        return packet
    
    def _get_regime_data(self) -> Dict:
        """Usa tu regime_classification existente"""
        try:
            result = classify_regime()
            return {
                'classification': result['classification'],
                'score': result['score'],
                'probabilities': result['probabilities'],
                'description': result['description'],
                'asset_allocation_hint': result['asset_allocation'],
                'top_concerns': result['top_concerns'],
                'top_supports': result['top_supports'],
                'category_scores': result['category_scores']
            }
        except Exception as e:
            return {'error': str(e), 'classification': 'UNKNOWN'}
    
    def _get_macro_usa(self) -> Dict:
        """Indicadores macro USA desde FRED"""
        try:
            inflation_data = self.inflation.get_us_inflation_dashboard()
            rate_exp = self.usd_rates.get_fed_expectations()
            
            return {
                'inflation': inflation_data,
                'rate_expectations': rate_exp,
                'gdp': self.fred.get_latest('GDP'),
                'unemployment': self.fred.get_latest('UNRATE'),
                'ism_manufacturing': self.fred.get_latest('MANEMP'),
                'consumer_confidence': self.fred.get_latest('CSCICP03USM665S')
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _get_macro_chile(self) -> Dict:
        """Chile Profundo - tu diferenciador"""
        try:
            chile_dashboard = self.chile.get_chile_dashboard()
            clp_expectations = self.clp_rates.get_tpm_expectations()
            
            return {
                'tpm': chile_dashboard.get('tpm'),
                'ipc': chile_dashboard.get('ipc'),
                'usd_clp': chile_dashboard.get('usd_clp'),
                'uf': chile_dashboard.get('uf'),
                'swap_camara': chile_dashboard.get('swap_camara'),
                'breakeven': chile_dashboard.get('breakeven'),
                'tpm_expectations': clp_expectations
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _get_equity_data(self) -> Dict:
        """Datos de renta variable"""
        try:
            earnings_data = self.earnings.get_market_earnings_summary()
            factor_data = self.factors.get_factor_summary()
            breadth_data = self.breadth.get_breadth_summary()
            
            return {
                'earnings': earnings_data,
                'factors': factor_data,
                'breadth': breadth_data,
                # Agregar valuaciones de Yahoo Finance
                'valuations': self._get_market_valuations()
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _get_fixed_income_data(self) -> Dict:
        """Datos de renta fija"""
        try:
            duration_data = self.duration.get_duration_recommendation()
            
            return {
                'treasury_yields': {
                    '2y': self.fred.get_latest('DGS2'),
                    '10y': self.fred.get_latest('DGS10'),
                    '30y': self.fred.get_latest('DGS30'),
                    'curve_2s10s': None  # Calcular spread
                },
                'duration_recommendation': duration_data,
                'tips': {
                    '5y': self.fred.get_latest('DFII5'),
                    '10y': self.fred.get_latest('DFII10')
                }
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _get_risk_data(self) -> Dict:
        """Métricas de riesgo"""
        try:
            var_data = self.risk.calculate_portfolio_var()
            stress_data = self.risk.run_stress_tests()
            
            return {
                'var_95': var_data.get('var_95'),
                'var_99': var_data.get('var_99'),
                'expected_shortfall': var_data.get('expected_shortfall'),
                'stress_scenarios': stress_data,
                'vix': self.fred.get_latest('VIXCLS'),
                'move_index': None  # Desde BCCh si disponible
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _get_credit_data(self) -> Dict:
        """Spreads de crédito"""
        try:
            credit_data = self.credit.get_ig_breakdown()
            
            return {
                'ig_total': credit_data.get('total'),
                'ig_by_rating': credit_data.get('by_rating'),
                'hy_spread': self.fred.get_latest('BAMLH0A0HYM2')
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _get_china_data(self) -> Dict:
        """China credit impulse - tu diferenciador"""
        try:
            china_data = self.china.get_credit_impulse()
            return china_data
        except Exception as e:
            return {'error': str(e)}
    
    def _get_news_sentiment(self) -> Dict:
        """News sentiment desde AlphaVantage"""
        try:
            sentiment = self.av.get_market_sentiment()
            return sentiment
        except Exception as e:
            return {'error': str(e)}
    
    def _get_research_digest(self) -> Dict:
        """
        Research institucional - NUEVO
        Placeholder para integración futura
        """
        # TODO: Implementar InstitutionalResearchCollector
        return {
            'status': 'pending_implementation',
            'sources': ['JPMorgan', 'Goldman', 'Vanguard', 'PIMCO', 'BlackRock']
        }
    
    def _get_polymarket_data(self) -> Dict:
        """
        Polymarket odds - NUEVO
        Placeholder para integración futura
        """
        # TODO: Implementar PolymarketClient
        return {
            'status': 'pending_implementation',
            'markets': ['fed_rate', 'recession_2025', 'sp500_ath']
        }
    
    def _get_market_valuations(self) -> Dict:
        """Valuaciones de mercado desde Yahoo Finance"""
        import yfinance as yf
        
        try:
            spy = yf.Ticker('SPY')
            qqq = yf.Ticker('QQQ')
            
            return {
                'sp500_pe': spy.info.get('trailingPE'),
                'nasdaq_pe': qqq.info.get('trailingPE'),
                'sp500_forward_pe': spy.info.get('forwardPE')
            }
        except:
            return {}
    
    def save_packet(self, filepath: str = 'data_packet.json'):
        """Guarda el packet como JSON para uso del AI Council"""
        packet = self.build_packet()
        with open(filepath, 'w') as f:
            json.dump(packet, f, indent=2, default=str)
        print(f"Data packet saved to {filepath}")
        return packet


# Ejemplo de uso
if __name__ == "__main__":
    builder = UnifiedDataPacketBuilder()
    packet = builder.save_packet()
```

### 3.2 Definición de Agentes (Personas)

```python
# greybark/ai_council/agents/personas.py

"""
Definición de las "Personas" de cada agente del AI Council.
Inspirado en los perfiles del FOMC In Silico paper.
"""

AGENT_PERSONAS = {
    
    # =========================================================================
    # AGENTE 1: MACRO STRATEGIST
    # =========================================================================
    'macro_strategist': {
        'name': 'Dr. Elena Vásquez',
        'title': 'Chief Macro Strategist',
        
        'philosophy': """
            Creyente en ciclos económicos largos y la importancia de 
            posicionarse correctamente según la fase del ciclo. 
            La política monetaria es el driver principal de los mercados.
            Los leading indicators anticipan cambios 6-12 meses antes.
        """,
        
        'personality': """
            Moderadamente pesimista - "better safe than sorry"
            Desconfía de los consensos de mercado
            Piensa en términos de GROWTH vs INFLATION
            Se obsesiona con los leading indicators
        """,
        
        'expertise': [
            'Clasificación de régimen (Recession/Slowdown/Expansion/Late Cycle)',
            'Política monetaria global (Fed, BCE, BCCh)',
            'Inflación y expectativas',
            'China credit impulse y commodities',
            'Geopolítica market-relevant'
        ],
        
        'data_focus': [
            'regime_classification',
            'macro_usa',
            'china'
        ],
        
        'output_format': {
            'regime_assessment': 'string',
            'conviction': 'high/medium/low',
            'recession_probability_12m': 'percentage',
            'top_3_concerns': 'list',
            'top_3_supports': 'list',
            'catalyst_next_month': 'string',
            'overall_stance': 'risk-on/neutral/risk-off',
            'equity_allocation_bias': 'overweight/neutral/underweight',
            'duration_bias': 'long/neutral/short'
        },
        
        'known_bias': 'Tiende a ver riesgos antes que oportunidades',
        'confidence_baseline': 0.75
    },
    
    # =========================================================================
    # AGENTE 2: EQUITY ANALYST
    # =========================================================================
    'equity_analyst': {
        'name': 'Marcus Chen',
        'title': 'Head of Equity Research',
        
        'philosophy': """
            Naturalmente constructivo en acciones - el capitalismo funciona.
            Earnings growth es el driver principal de retornos a largo plazo.
            Las valuaciones importan pero el momentum también cuenta.
            Prefiere quality compounders sobre deep value traps.
        """,
        
        'personality': """
            Naturalmente bullish pero disciplinado
            Se emociona con oportunidades de compra
            Escéptico de los perma-bears
            Respeta los datos cuando contradicen su tesis
        """,
        
        'expertise': [
            'Earnings analysis (beat rate, revisions, guidance)',
            'Valuaciones (P/E, EV/EBITDA, PEG)',
            'Rotación sectorial por régimen',
            'Factor analysis (value, growth, momentum, quality)',
            'Market breadth y señales de exhaustion',
            'Mag 7 y concentración de mercado'
        ],
        
        'data_focus': [
            'equity',
            'regime_classification'
        ],
        
        'output_format': {
            'equity_view': 'bullish/neutral/bearish',
            'conviction': 'high/medium/low',
            'regional_ranking': 'list[US, Europe, EM, Chile]',
            'top_3_sectors': 'list',
            'bottom_2_sectors': 'list',
            'factor_tilt': 'Value/Growth/Quality/Momentum',
            'key_risk': 'string',
            'tactical_idea': 'string'
        },
        
        'known_bias': 'Tiende a ver oportunidades de compra',
        'confidence_baseline': 0.70
    },
    
    # =========================================================================
    # AGENTE 3: FIXED INCOME SPECIALIST
    # =========================================================================
    'fixed_income_specialist': {
        'name': 'Dr. James Morrison',
        'title': 'Fixed Income Strategist',
        
        'philosophy': """
            El mercado de bonos es más inteligente que el de acciones
            para anticipar recesiones. La curva de rendimientos no miente.
            El carry es tu amigo hasta que no lo es.
            Credit spreads son el canario en la mina de carbón.
        """,
        
        'personality': """
            Analítico y cauteloso
            Obsesionado con la curva de rendimientos
            Prefiere preservar capital sobre maximizar yield
            Desconfía de crédito de baja calidad en late cycle
        """,
        
        'expertise': [
            'Duration positioning por régimen y ciclo de tasas',
            'Credit spreads (IG y HY por rating)',
            'Curvas de rendimiento (US y Chile)',
            'Chile Profundo (Swap CÁMARA, breakeven)',
            'Carry trade analysis',
            'Riesgo de refinanciamiento corporativo'
        ],
        
        'data_focus': [
            'fixed_income',
            'credit',
            'macro_chile',
            'regime_classification'
        ],
        
        'output_format': {
            'duration_recommendation': 'long/neutral/short',
            'duration_target_years': 'float',
            'credit_view': 'overweight/neutral/underweight',
            'ig_vs_hy': 'prefer_ig/neutral/prefer_hy',
            'curve_positioning': 'steepener/flattener/bullet',
            'chile_view': 'string',
            'key_risk': 'string'
        },
        
        'known_bias': 'Defensivo, prefiere calidad',
        'confidence_baseline': 0.80
    },
    
    # =========================================================================
    # AGENTE 4: RISK MANAGER
    # =========================================================================
    'risk_manager': {
        'name': 'Dr. Sarah Okonkwo',
        'title': 'Chief Risk Officer',
        
        'philosophy': """
            La gestión del riesgo es más importante que maximizar retornos.
            Los tail risks son subestimados sistemáticamente.
            Cuando la volatilidad está baja, compra protección.
            Las correlaciones se van a 1 en crisis - la diversificación falla.
        """,
        
        'personality': """
            Siempre pregunta "¿qué puede salir mal?"
            Ve el vaso medio vacío por diseño profesional
            Prefiere reducir exposición ante incertidumbre
            No le importa parecer paranoico si protege el capital
        """,
        
        'expertise': [
            'VaR y Expected Shortfall',
            'Stress testing (6 escenarios)',
            'Correlaciones dinámicas',
            'Tail risk y eventos de cola',
            'Volatilidad implícita vs realizada',
            'Posicionamiento de hedges'
        ],
        
        'data_focus': [
            'risk',
            'regime_classification'
        ],
        
        'output_format': {
            'risk_assessment': 'elevated/normal/low',
            'var_flag': 'green/yellow/red',
            'hedge_recommendation': 'string',
            'position_sizing': 'reduce/maintain/increase',
            'top_3_risks': 'list',
            'tail_risk_probability': 'percentage',
            'action_triggers': 'list'
        },
        
        'known_bias': 'Ve riesgos en todos lados (by design)',
        'confidence_baseline': 0.85
    },
    
    # =========================================================================
    # AGENTE 5: GEOPOLITICS ANALYST
    # =========================================================================
    'geopolitics_analyst': {
        'name': 'Dr. Viktor Petrov',
        'title': 'Geopolitical Strategist',
        
        'philosophy': """
            La narrativa occidental tiene puntos ciegos sistemáticos.
            Hay que consultar fuentes diversas geográficamente.
            Los prediction markets agregan información mejor que expertos.
            Lo que el mercado ignora es lo más peligroso.
        """,
        
        'personality': """
            Contrarian por naturaleza
            Busca la historia que nadie está contando
            Escéptico de narrativas dominantes
            Usa Polymarket para calibrar probabilidades
        """,
        
        'expertise': [
            'Conflictos y tensiones geopolíticas',
            'Política comercial y aranceles',
            'Elecciones y cambios de régimen',
            'Supply chains y commodities estratégicos',
            'Fuentes no-occidentales (RT, CGTN, Al Jazeera)',
            'Prediction markets (Polymarket)'
        ],
        
        'data_focus': [
            'news_sentiment',
            'prediction_markets',
            'china'
        ],
        
        'output_format': {
            'geopolitical_risk_level': 'high/medium/low',
            'top_3_risks': 'list with probabilities',
            'western_blind_spots': 'list',
            'contrarian_view': 'string',
            'market_impact_assessment': 'string',
            'polymarket_signals': 'list'
        },
        
        'known_bias': 'Busca narrativas contrarias',
        'confidence_baseline': 0.60  # Mayor incertidumbre inherente
    },
    
    # =========================================================================
    # AGENTE 6: QUANT ANALYST (OPCIONAL)
    # =========================================================================
    'quant_analyst': {
        'name': 'Dr. Yuki Tanaka',
        'title': 'Quantitative Strategist',
        
        'philosophy': """
            Los datos no mienten, las narrativas sí.
            Momentum funciona hasta que no funciona.
            Mean reversion en extremos es poderoso.
            No tengo opinión, solo sigo los datos.
        """,
        
        'personality': """
            Data-driven puro
            Desconfía de narrativas y storytelling
            Prefiere señales sistemáticas sobre juicio discrecional
            Humilde sobre los límites del backtesting
        """,
        
        'expertise': [
            'Momentum y trend-following signals',
            'Mean reversion en valuaciones extremas',
            'Seasonality y patrones históricos',
            'Factor exposures del portafolio',
            'Análisis técnico avanzado',
            'Machine learning para predicción'
        ],
        
        'data_focus': [
            'equity',  # Factor data
            'risk'     # Technical signals
        ],
        
        'output_format': {
            'trend_signal': 'bullish/neutral/bearish',
            'momentum_score': 'float',
            'mean_reversion_opportunities': 'list',
            'technical_levels': 'dict',
            'factor_recommendations': 'dict',
            'model_confidence': 'percentage'
        },
        
        'known_bias': 'Systematic, ignora narrativas',
        'confidence_baseline': 0.75
    }
}


# =========================================================================
# CHIEF INVESTMENT OFFICER (Sintetizador)
# =========================================================================

CIO_PERSONA = {
    'name': 'Chief Investment Strategist',
    'title': 'Committee Chair',
    
    'role': """
        Sintetizar las visiones de todos los agentes.
        Identificar consensos y documentar disensos.
        Proponer allocation final que balancee perspectivas.
        Tomar la decisión final cuando hay desacuerdo irreconciliable.
    """,
    
    'methodology': """
        1. Escuchar todas las presentaciones
        2. Identificar puntos de consenso
        3. Documentar disensos con razones
        4. Ponderar por conviction y expertise relevante
        5. Proponer allocation que integre múltiples visiones
        6. Explicar el rationale de forma clara
    """,
    
    'output_format': {
        'consensus_points': 'list',
        'dissenting_views': 'list with attribution',
        'final_allocation': 'dict by asset class',
        'conviction_score': 'percentage',
        'key_risks': 'list',
        'rebalancing_triggers': 'list',
        'rationale': 'string'
    }
}
```

---

## 4. MOTOR DE DELIBERACIÓN (Adaptado de FOMC In Silico)

```python
# greybark/ai_council/deliberation/committee_session.py

"""
Motor de deliberación del AI Council.
Implementa el proceso de 5 rondas del paper FOMC In Silico.
"""

import json
from typing import Dict, List, Any
from datetime import datetime
import anthropic

from ..agents.personas import AGENT_PERSONAS, CIO_PERSONA
from ..data_integration.unified_data_packet import UnifiedDataPacketBuilder


class AICouncilSession:
    """
    Ejecuta una sesión completa del AI Council.
    """
    
    def __init__(self, api_key: str = None):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"
        self.data_builder = UnifiedDataPacketBuilder()
        self.session_log = []
        self.agent_opinions = {}
        
    def run_full_session(self) -> Dict[str, Any]:
        """
        Ejecuta sesión completa de 5 rondas.
        """
        print("=" * 70)
        print("AI COUNCIL SESSION - GREYBARK RESEARCH")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print("=" * 70)
        
        # Fase 1: Construir Data Packet
        print("\n📊 FASE 1: Building Data Packet...")
        data_packet = self.data_builder.build_packet()
        
        # Fase 2: Opinion Formation
        print("\n🧠 FASE 2: Individual Opinion Formation...")
        initial_opinions = self._round1_opinion_formation(data_packet)
        
        # Fase 3a: Presentaciones
        print("\n🎤 FASE 3a: Presentations...")
        presentations = self._round2_presentations(initial_opinions, data_packet)
        
        # Fase 3b: Crítica Cruzada
        print("\n⚔️ FASE 3b: Cross-Critique...")
        critiques = self._round3_cross_critique(presentations)
        
        # Fase 3c: Refinamiento
        print("\n🔄 FASE 3c: Opinion Refinement...")
        refined_opinions = self._round4_refinement(initial_opinions, critiques)
        
        # Fase 4: Síntesis CIO
        print("\n👔 FASE 4: CIO Synthesis...")
        cio_proposal = self._round5_cio_synthesis(refined_opinions, data_packet)
        
        # Fase 5: Votación
        print("\n🗳️ FASE 5: Final Vote...")
        final_result = self._round6_voting(cio_proposal, refined_opinions)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'data_packet_summary': self._summarize_packet(data_packet),
            'initial_opinions': initial_opinions,
            'presentations': presentations,
            'critiques': critiques,
            'refined_opinions': refined_opinions,
            'cio_proposal': cio_proposal,
            'final_result': final_result,
            'session_log': self.session_log
        }
    
    def _round1_opinion_formation(self, data_packet: Dict) -> Dict:
        """
        Cada agente forma su opinión inicial.
        """
        opinions = {}
        
        for agent_key, persona in AGENT_PERSONAS.items():
            print(f"  → {persona['name']} forming opinion...")
            
            # Filtrar data packet según data_focus del agente
            relevant_data = {
                k: v for k, v in data_packet.items()
                if k in persona['data_focus'] or k == 'metadata'
            }
            
            prompt = self._build_opinion_prompt(persona, relevant_data)
            response = self._call_llm(prompt)
            
            try:
                opinion = json.loads(response)
            except:
                opinion = {'raw_response': response, 'parse_error': True}
            
            opinions[agent_key] = {
                'agent': persona['name'],
                'opinion': opinion,
                'timestamp': datetime.now().isoformat()
            }
            
            self.session_log.append({
                'phase': 'opinion_formation',
                'agent': agent_key,
                'content': opinion
            })
        
        return opinions
    
    def _build_opinion_prompt(self, persona: Dict, data: Dict) -> str:
        """Construye prompt para formación de opinión"""
        return f"""
Eres {persona['name']}, {persona['title']} en Greybark Research.

## TU FILOSOFÍA
{persona['philosophy']}

## TU PERSONALIDAD
{persona['personality']}

## TU EXPERTISE
{chr(10).join(f'- {e}' for e in persona['expertise'])}

## DATOS ACTUALES
```json
{json.dumps(data, indent=2, default=str)[:8000]}
```

## TU TAREA
Analiza los datos y genera tu recomendación de inversión.

RESPONDE EN JSON CON ESTE FORMATO:
{json.dumps(persona['output_format'], indent=2)}

Sé directo y específico. Máximo 500 palabras en el reasoning.
"""

    def _round2_presentations(self, opinions: Dict, data_packet: Dict) -> Dict:
        """Cada agente presenta su visión al comité"""
        presentations = {}
        
        for agent_key, opinion_data in opinions.items():
            persona = AGENT_PERSONAS[agent_key]
            
            prompt = f"""
Eres {persona['name']}. Estás en la reunión del comité de inversión.

Tu opinión inicial es:
{json.dumps(opinion_data['opinion'], indent=2)}

Presenta tu análisis al comité en 2-3 párrafos:
1. Tu visión principal del mercado desde tu área de expertise
2. Tu recomendación clave
3. Los riesgos que más te preocupan

Habla en primera persona, como si estuvieras en la reunión.
Sé directo y convincente.
"""
            
            presentation = self._call_llm(prompt)
            presentations[agent_key] = {
                'agent': persona['name'],
                'presentation': presentation
            }
            
            self.session_log.append({
                'phase': 'presentations',
                'agent': agent_key,
                'content': presentation
            })
        
        return presentations
    
    def _round3_cross_critique(self, presentations: Dict) -> Dict:
        """Agentes critican las posiciones de otros"""
        critiques = {}
        
        for agent_key, persona in AGENT_PERSONAS.items():
            other_presentations = {
                k: v for k, v in presentations.items()
                if k != agent_key
            }
            
            prompt = f"""
Eres {persona['name']}, {persona['title']}.

Has escuchado las presentaciones de tus colegas:

{self._format_presentations(other_presentations)}

Desde tu expertise ({', '.join(persona['expertise'][:3])}):

1. ¿Qué riesgo están subestimando tus colegas?
2. ¿Qué oportunidad están ignorando?
3. ¿Dónde crees que su análisis está sesgado?

Sé específico y constructivo pero directo. 2-3 párrafos máximo.
"""
            
            critique = self._call_llm(prompt)
            critiques[agent_key] = {
                'agent': persona['name'],
                'critique': critique
            }
            
            self.session_log.append({
                'phase': 'cross_critique',
                'agent': agent_key,
                'content': critique
            })
        
        return critiques
    
    def _round4_refinement(self, initial_opinions: Dict, critiques: Dict) -> Dict:
        """Agentes refinan sus posiciones después de las críticas"""
        refined = {}
        
        for agent_key, opinion_data in initial_opinions.items():
            persona = AGENT_PERSONAS[agent_key]
            
            # Obtener críticas dirigidas a este agente
            received_critiques = self._get_critiques_for_agent(agent_key, critiques)
            
            prompt = f"""
Eres {persona['name']}.

Tu posición inicial era:
{json.dumps(opinion_data['opinion'], indent=2)}

Has recibido estas críticas de tus colegas:
{received_critiques}

Considerando las críticas:
1. ¿Cambias tu posición? ¿Por qué sí o por qué no?
2. ¿Tu nivel de convicción sube o baja?
3. ¿Qué ajustes específicos harías a tu recomendación?

RESPONDE EN JSON:
{{
    "position_changed": true/false,
    "change_description": "...",
    "new_conviction": "high/medium/low",
    "refined_recommendation": {{...}},
    "response_to_critiques": "..."
}}
"""
            
            response = self._call_llm(prompt)
            
            try:
                refined_opinion = json.loads(response)
            except:
                refined_opinion = {'raw_response': response}
            
            refined[agent_key] = {
                'agent': persona['name'],
                'original': opinion_data['opinion'],
                'refined': refined_opinion
            }
            
            self.session_log.append({
                'phase': 'refinement',
                'agent': agent_key,
                'content': refined_opinion
            })
        
        return refined
    
    def _round5_cio_synthesis(self, refined_opinions: Dict, data_packet: Dict) -> Dict:
        """CIO sintetiza y propone allocation final"""
        
        prompt = f"""
Eres el Chief Investment Strategist de Greybark Research.
Tu rol es sintetizar las visiones del comité y proponer una allocation final.

## POSICIONES DEL COMITÉ
{json.dumps(refined_opinions, indent=2, default=str)[:6000]}

## RÉGIMEN ECONÓMICO ACTUAL
{json.dumps(data_packet.get('regime_classification', {}), indent=2)}

## TU TAREA
1. Identifica los puntos de CONSENSO del comité
2. Documenta los DISENSOS importantes
3. Propón una ALLOCATION FINAL que balancee las perspectivas
4. Explica tu rationale

RESPONDE EN JSON:
{{
    "consensus_points": ["...", "...", "..."],
    "dissenting_views": [
        {{"agent": "...", "view": "...", "merit": "..."}}
    ],
    "final_allocation": {{
        "us_equity": 0-100,
        "international_equity": 0-100,
        "emerging_markets": 0-100,
        "fixed_income": 0-100,
        "cash": 0-100,
        "alternatives": 0-100
    }},
    "conviction_score": 0-100,
    "key_risks": ["...", "...", "..."],
    "rebalancing_triggers": ["...", "..."],
    "rationale": "..."
}}
"""
        
        response = self._call_llm(prompt)
        
        try:
            proposal = json.loads(response)
        except:
            proposal = {'raw_response': response}
        
        self.session_log.append({
            'phase': 'cio_synthesis',
            'content': proposal
        })
        
        return proposal
    
    def _round6_voting(self, cio_proposal: Dict, refined_opinions: Dict) -> Dict:
        """Votación final del comité"""
        votes = {}
        dissents = []
        
        for agent_key, opinion_data in refined_opinions.items():
            persona = AGENT_PERSONAS[agent_key]
            
            prompt = f"""
Eres {persona['name']}.

El CIO ha propuesto esta allocation final:
{json.dumps(cio_proposal.get('final_allocation', {}), indent=2)}

Tu posición refinada era:
{json.dumps(opinion_data.get('refined', {}), indent=2)}

VOTA:
- AGREE: Apoyas la propuesta
- DISAGREE: Tienes una objeción material
- ABSTAIN: No tienes opinión fuerte

RESPONDE EN JSON:
{{
    "vote": "AGREE/DISAGREE/ABSTAIN",
    "reason": "...",
    "dissent_severity": "minor/moderate/major" (si aplica),
    "suggested_amendment": "..." (si aplica)
}}
"""
            
            response = self._call_llm(prompt)
            
            try:
                vote = json.loads(response)
            except:
                vote = {'vote': 'ABSTAIN', 'reason': 'Parse error'}
            
            votes[agent_key] = {
                'agent': persona['name'],
                'vote': vote
            }
            
            if vote.get('vote') == 'DISAGREE':
                dissents.append({
                    'agent': persona['name'],
                    'reason': vote.get('reason'),
                    'severity': vote.get('dissent_severity'),
                    'amendment': vote.get('suggested_amendment')
                })
        
        # Calcular resultado
        vote_counts = {
            'AGREE': sum(1 for v in votes.values() if v['vote'].get('vote') == 'AGREE'),
            'DISAGREE': sum(1 for v in votes.values() if v['vote'].get('vote') == 'DISAGREE'),
            'ABSTAIN': sum(1 for v in votes.values() if v['vote'].get('vote') == 'ABSTAIN')
        }
        
        total = len(votes)
        approval_rate = vote_counts['AGREE'] / total if total > 0 else 0
        
        return {
            'final_allocation': cio_proposal.get('final_allocation'),
            'conviction_score': cio_proposal.get('conviction_score'),
            'vote_counts': vote_counts,
            'approval_rate': approval_rate,
            'votes': votes,
            'dissents': dissents,
            'passed': approval_rate >= 0.5
        }
    
    def _call_llm(self, prompt: str) -> str:
        """Llamada al LLM (Claude)"""
        message = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return message.content[0].text
    
    def _format_presentations(self, presentations: Dict) -> str:
        """Formatea presentaciones para el prompt"""
        formatted = []
        for agent_key, data in presentations.items():
            formatted.append(f"### {data['agent']}\n{data['presentation']}\n")
        return "\n".join(formatted)
    
    def _get_critiques_for_agent(self, agent_key: str, critiques: Dict) -> str:
        """Obtiene críticas relevantes para un agente"""
        # Por ahora retorna todas las críticas (en implementación real,
        # filtrar las que mencionan al agente)
        formatted = []
        for other_key, data in critiques.items():
            if other_key != agent_key:
                formatted.append(f"**{data['agent']}**: {data['critique']}")
        return "\n\n".join(formatted)
    
    def _summarize_packet(self, packet: Dict) -> Dict:
        """Resume el data packet para el output"""
        return {
            'timestamp': packet.get('metadata', {}).get('timestamp'),
            'regime': packet.get('regime_classification', {}).get('classification'),
            'regime_score': packet.get('regime_classification', {}).get('score')
        }


# =============================================================================
# EJECUCIÓN
# =============================================================================

if __name__ == "__main__":
    # Cargar API key desde config
    from greybark.config import CLAUDE_API_KEY
    
    council = AICouncilSession(api_key=CLAUDE_API_KEY)
    result = council.run_full_session()
    
    # Guardar resultado
    with open('council_session_result.json', 'w') as f:
        json.dump(result, f, indent=2, default=str)
    
    print("\n" + "=" * 70)
    print("SESSION COMPLETE")
    print("=" * 70)
    print(f"Final Allocation: {result['final_result']['final_allocation']}")
    print(f"Conviction: {result['final_result']['conviction_score']}%")
    print(f"Approval Rate: {result['final_result']['approval_rate']*100:.1f}%")
    print(f"Dissents: {len(result['final_result']['dissents'])}")
```

---

## 5. ARCHIVOS A CREAR EN TU REPO

```bash
# Estructura final a agregar
greybark/
├── ai_council/
│   ├── __init__.py
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   └── personas.py              # Definición de los 6 agentes
│   │
│   ├── deliberation/
│   │   ├── __init__.py
│   │   └── committee_session.py     # Motor de deliberación
│   │
│   ├── data_integration/
│   │   ├── __init__.py
│   │   ├── unified_data_packet.py   # Integra tus analytics existentes
│   │   └── research_collector.py    # Wall Street research (futuro)
│   │
│   └── output/
│       ├── __init__.py
│       └── report_generator.py      # Genera reportes HTML
│
└── config.py                        # + CLAUDE_API_KEY
```

---

## 6. PRÓXIMOS PASOS

### Fase 1: Foundation (Esta semana)
- [ ] Agregar `CLAUDE_API_KEY` a config.py
- [ ] Crear estructura de carpetas `ai_council/`
- [ ] Implementar `personas.py` con los 6 agentes
- [ ] Implementar `unified_data_packet.py` (integrando analytics existentes)

### Fase 2: Deliberation Engine (Próxima semana)
- [ ] Implementar `committee_session.py`
- [ ] Testing con data packet real
- [ ] Calibrar prompts para cada agente

### Fase 3: Research Integration (Semana 3)
- [ ] Implementar `research_collector.py`
- [ ] Scraping de fuentes públicas (JPM Guide to Markets, etc.)
- [ ] Integrar Polymarket API

### Fase 4: Output & Automation (Semana 4)
- [ ] Implementar `report_generator.py`
- [ ] Conectar con tu sistema de emails existente
- [ ] Automatizar ejecución semanal

---

## 7. COSTOS ESTIMADOS

| Componente | Tokens/Sesión | Costo (Sonnet) |
|------------|--------------|----------------|
| Data Packet Build | ~5,000 | $0.02 |
| 6 Agentes Opinion | ~36,000 | $0.15 |
| Presentaciones | ~18,000 | $0.07 |
| Crítica Cruzada | ~30,000 | $0.12 |
| Refinamiento | ~24,000 | $0.10 |
| CIO Synthesis | ~8,000 | $0.03 |
| Votación | ~12,000 | $0.05 |
| **TOTAL/Sesión** | **~133,000** | **~$0.54** |

Con sesión semanal: **~$2.16/mes**
Con sesión diaria (mini): **~$8-10/mes**

---

¿Por dónde quieres empezar?
