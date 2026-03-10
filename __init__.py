# -*- coding: utf-8 -*-
"""
Greybark Research - Consejo IA
===============================

Sistema de AI Investment Council con reportes automatizados.

Módulos principales:
    - ai_council_runner: Orquestador del AI Council (5 panel + 3 sintesis)
    - council_data_collector: 10 módulos cuantitativos macro
    - forecast_engine: Motor de pronósticos (surveys + econométrico)
    - econometric_models: ARIMA, VAR, Taylor Rule, Phillips Curve

Data Collectors:
    - equity_data_collector: 10 módulos equity (yfinance/AV/BCCh)
    - rf_data_collector: 12 módulos renta fija (FRED/BCCh)
    - daily_intelligence_digest: Digesto reportes diarios

Content Generators + Renderers:
    - macro_content_generator / macro_report_renderer
    - rv_content_generator / rv_report_renderer
    - rf_content_generator / rf_report_renderer
    - asset_allocation_content_generator / asset_allocation_renderer

Pipeline:
    - run_monthly: Pipeline mensual unificado (5 fases)

Uso:
    from consejo_ia import AICouncilRunner, ForecastEngine

    runner = AICouncilRunner()
    result = runner.run_session_sync(report_type='macro')

    engine = ForecastEngine()
    forecasts = engine.generate_all(equity_data, rf_data, quant_data)
"""

from .ai_council_runner import AICouncilRunner
from .council_data_collector import CouncilDataCollector
from .daily_report_parser import DailyReportParser
from .forecast_engine import ForecastEngine
from .econometric_models import EconometricSuite

__all__ = [
    'AICouncilRunner',
    'CouncilDataCollector',
    'DailyReportParser',
    'ForecastEngine',
    'EconometricSuite',
]

__version__ = '2.0.0'
