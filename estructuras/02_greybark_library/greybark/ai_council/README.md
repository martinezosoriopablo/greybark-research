# Greybark Research - AI Council Module

## 🎯 Descripción

El **AI Council** es un sistema multi-agente para decisiones de inversión basado en el paper académico ["FOMC In Silico: A Multi-Agent System for Monetary Policy Decision Modeling"](https://www2.gwu.edu/~forcpgm/2025-005.pdf) de Kazinnik & Sinclair (2025).

Replica un **comité de inversión profesional** donde 6 agentes especializados:
1. Forman opiniones individuales
2. Presentan sus análisis
3. Critican las posiciones de otros
4. Refinan sus opiniones
5. Votan sobre una propuesta final

## 📁 Estructura

```
greybark/ai_council/
├── __init__.py
├── agents/
│   ├── __init__.py
│   └── personas.py           # 6 agentes con personalidades definidas
├── deliberation/
│   ├── __init__.py
│   └── committee_session.py  # Motor de deliberación (5 rondas)
├── data_integration/
│   ├── __init__.py
│   └── unified_data_packet.py # Integra greybark.analytics
└── output/
    └── __init__.py           # TODO: Report generator
```

## 🚀 Instalación

```bash
# 1. Instalar dependencia de Claude
pip install anthropic

# 2. Configurar API key (una de estas opciones):

# Opción A: Environment variable
export ANTHROPIC_API_KEY="tu-api-key"

# Opción B: En greybark/config.py
# Editar ClaudeConfig.api_key = "tu-api-key"
```

## 💻 Uso Básico

```python
from greybark.ai_council import AICouncilSession

# Crear sesión
council = AICouncilSession()

# Ejecutar deliberación completa
result = council.run_full_session()

# Ver resultado
print(f"Allocation: {result['final_result']['final_allocation']}")
print(f"Conviction: {result['final_result']['conviction_score']}%")
print(f"Dissents: {len(result['final_result']['dissents'])}")
```

## 👥 Los 6 Agentes

| Agente | Nombre | Expertise | Sesgo Natural |
|--------|--------|-----------|---------------|
| `macro_strategist` | Dr. Elena Vásquez | Ciclos, Fed, Régimen | Cauteloso |
| `equity_analyst` | Marcus Chen | Earnings, Valuaciones, Sectores | Bullish |
| `fixed_income_specialist` | Dr. James Morrison | Duration, Credit, Chile Profundo | Defensivo |
| `risk_manager` | Dr. Sarah Okonkwo | VaR, Stress Tests, Tail Risk | Risk-averse |
| `geopolitics_analyst` | Dr. Viktor Petrov | Non-Western sources, Polymarket | Contrarian |
| `quant_analyst` | Dr. Yuki Tanaka | Momentum, Factors, Technicals | Data-driven |

## 🔄 Proceso de Deliberación (5 Rondas)

```
┌─────────────────────────────────────────────────────────────────┐
│ RONDA 1: OPINION FORMATION                                      │
│ Cada agente forma su opinión basada en el Data Packet           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ RONDA 2: PRESENTATIONS                                          │
│ Cada agente presenta su visión al comité                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ RONDA 3: CROSS-CRITIQUE                                         │
│ Agentes critican las posiciones de otros                        │
│ "Macro critica a Equity: Ignoras riesgo de recesión"            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ RONDA 4: REFINEMENT                                             │
│ Agentes actualizan opiniones basado en críticas                 │
│ (Bayesian updating del paper FOMC)                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ RONDA 5: CIO SYNTHESIS + VOTING                                 │
│ Chief Investment Officer sintetiza y propone allocation         │
│ Cada agente vota: AGREE / DISAGREE / ABSTAIN                    │
│ Se documentan disensos (¡valor único!)                          │
└─────────────────────────────────────────────────────────────────┘
```

## 📊 Output

El resultado de `run_full_session()` incluye:

```python
{
    'metadata': {...},
    'data_packet_summary': {...},
    'initial_opinions': {...},
    'presentations': {...},
    'critiques': {...},
    'refined_opinions': {...},
    'cio_proposal': {...},
    'final_result': {
        'final_allocation': {
            'us_equity': 35,
            'international_equity_developed': 15,
            'emerging_markets': 10,
            'fixed_income_government': 20,
            'fixed_income_credit': 10,
            'cash': 5,
            'alternatives': 5
        },
        'conviction_score': 75,
        'approval_rate': 0.83,
        'dissents': [
            {'agent': 'Dr. Sarah Okonkwo', 'reason': '...', 'severity': 'moderate'}
        ],
        'consensus_points': [...],
        'key_risks': [...],
        'rebalancing_triggers': [...]
    },
    'session_log': [...]  # Log completo de la sesión
}
```

## 💰 Costos Estimados

| Frecuencia | Tokens/Sesión | Costo (Sonnet) |
|------------|--------------|----------------|
| Por sesión | ~130,000 | ~$0.54 |
| Semanal | ~520,000/mes | ~$2.16/mes |
| Diario (mini) | ~2.5M/mes | ~$10/mes |

## 🔗 Integración con greybark.analytics

El Data Packet integra automáticamente todos los módulos existentes:

- `regime_classification` → Régimen económico actual
- `macro` → Inflación analytics
- `risk` → VaR, stress tests
- `credit` → IG/HY spreads
- `chile` → Chile Profundo (Swap CÁMARA, breakeven)
- `china` → Credit impulse
- `earnings` → Beat rate, revisions
- `factors` → Value/Growth/Momentum/Quality
- `breadth` → Market breadth signals

## 🛠️ Próximos Pasos

1. **Integrar Research Institucional** - JPMorgan, Goldman, PIMCO, etc.
2. **Integrar Polymarket** - Prediction market odds
3. **Report Generator** - Generar HTML/PDF automáticamente
4. **Track Record** - Conectar con sistema de accountability

## 📚 Referencias

- Kazinnik, S., & Sinclair, T. M. (2025). *FOMC In Silico: A Multi-Agent System for Monetary Policy Decision Modeling*. GWU Working Paper No. 2025-005.

---

**Greybark Research** | AI-Powered Investment Research
