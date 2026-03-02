# -*- coding: utf-8 -*-
"""
Test de Charts - Greybark Research
Genera una pagina HTML con todos los charts de ejemplo.
"""

from chart_generator import ChartGenerator, MacroChartsGenerator
from pathlib import Path

def generate_test_page():
    """Genera pagina HTML con charts de prueba."""

    gen = ChartGenerator()

    # 1. Yield Curve - con curva actual, mes anterior, y hace 1 ano
    current = {'3M': 4.32, '6M': 4.28, '1Y': 4.15, '2Y': 4.05, '5Y': 4.00, '10Y': 4.15, '30Y': 4.35}
    previous_month = {'3M': 4.48, '6M': 4.40, '1Y': 4.30, '2Y': 4.20, '5Y': 4.10, '10Y': 4.20, '30Y': 4.40}
    previous_year = {'3M': 5.25, '6M': 5.10, '1Y': 4.85, '2Y': 4.55, '5Y': 4.25, '10Y': 4.35, '30Y': 4.50}  # Feb 2025
    yield_curve = gen.generate_yield_curve(current, previous_month, previous_year)

    # 2. GDP Comparison
    gdp_data = [
        {'region': 'USA', 'actual': '2.4%', 'forecast': '2.2%', 'consenso': '2.0%'},
        {'region': 'Euro Area', 'actual': '1.2%', 'forecast': '1.4%', 'consenso': '1.2%'},
        {'region': 'China', 'actual': '4.8%', 'forecast': '4.5%', 'consenso': '4.3%'},
        {'region': 'Chile', 'actual': '2.3%', 'forecast': '2.5%', 'consenso': '2.2%'},
    ]
    gdp_chart = gen.generate_gdp_comparison(gdp_data)

    # 3. Inflation Decomposition
    inflation_components = [
        {'nombre': 'Shelter', 'valor': '5.1%'},
        {'nombre': 'Services ex-Housing', 'valor': '3.5%'},
        {'nombre': 'Food', 'valor': '2.1%'},
        {'nombre': 'Core Goods', 'valor': '-0.3%'},
        {'nombre': 'Energy', 'valor': '-2.5%'},
    ]
    inflation_chart = gen.generate_inflation_decomposition(inflation_components)

    # 4. Scenarios Pie
    scenarios = [
        {'nombre': 'Soft Landing', 'probabilidad': '55%'},
        {'nombre': 'No Landing', 'probabilidad': '20%'},
        {'nombre': 'Hard Landing', 'probabilidad': '25%'},
    ]
    scenarios_chart = gen.generate_scenarios_pie(scenarios)

    # 5. Commodities
    commodities = [
        {'nombre': 'Cobre', 'cambio': '+3.6%'},
        {'nombre': 'Litio', 'cambio': '-16.7%'},
        {'nombre': 'Petroleo', 'cambio': '-4.9%'},
        {'nombre': 'Oro', 'cambio': '+2.1%'},
    ]
    commodities_chart = gen.generate_commodities_chart(commodities)

    # 6. Risk Matrix
    risks = [
        {'nombre': 'Escalada US-China', 'probabilidad': '30%', 'impacto': 'Alto'},
        {'nombre': 'Inflacion Sticky', 'probabilidad': '25%', 'impacto': 'Medio-Alto'},
        {'nombre': 'Crisis Fiscal', 'probabilidad': '20%', 'impacto': 'Medio'},
    ]
    risk_chart = gen.generate_risk_matrix(risks)

    # Generar HTML
    html = f'''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Greybark Research - Test Charts</title>
    <style>
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f7fafc;
        }}
        h1 {{
            color: #1a365d;
            border-bottom: 3px solid #dd6b20;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #2c5282;
            margin-top: 30px;
        }}
        .chart-container {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .chart-container img {{
            max-width: 100%;
            height: auto;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
        }}
        @media (max-width: 900px) {{
            .grid {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <h1>Greybark Research - Charts Preview</h1>
    <p>Generados: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}</p>

    <h2>1. US Treasury Yield Curve</h2>
    <div class="chart-container">
        <img src="{yield_curve}" alt="Yield Curve">
    </div>

    <h2>2. GDP Growth Comparison</h2>
    <div class="chart-container">
        <img src="{gdp_chart}" alt="GDP Comparison">
    </div>

    <h2>3. US Inflation Decomposition</h2>
    <div class="chart-container">
        <img src="{inflation_chart}" alt="Inflation Decomposition">
    </div>

    <div class="grid">
        <div>
            <h2>4. Scenario Probabilities</h2>
            <div class="chart-container">
                <img src="{scenarios_chart}" alt="Scenarios">
            </div>
        </div>

        <div>
            <h2>5. Commodities Performance</h2>
            <div class="chart-container">
                <img src="{commodities_chart}" alt="Commodities">
            </div>
        </div>
    </div>

    <h2>6. Risk Assessment Matrix</h2>
    <div class="chart-container">
        <img src="{risk_chart}" alt="Risk Matrix">
    </div>

    <footer style="margin-top: 40px; text-align: center; color: #718096;">
        Greybark Research | Charts Test Page
    </footer>
</body>
</html>
'''

    # Guardar
    output_path = Path(__file__).parent / 'output' / 'test_charts.html'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding='utf-8')

    print(f"Charts generados exitosamente!")
    print(f"Archivo: {output_path}")
    print(f"Abrelo en tu navegador para ver los graficos.")

    return str(output_path)


if __name__ == "__main__":
    generate_test_page()
