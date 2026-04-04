# -*- coding: utf-8 -*-
"""
Greybark Research — Crisis Episode Reference Table
====================================================

Provides verified historical crisis data for AI council agents.
Agents use these as calibration anchors for probability estimation
and forward-looking analysis.

Usage:
    from crisis_reference import get_crisis_reference_text

    text = get_crisis_reference_text()
    # Returns formatted text for injection into agent prompts
"""


# Historical crisis episodes with verified market impacts
CRISIS_EPISODES = [
    {
        'name': 'GFC (Crisis Financiera Global)',
        'period': '2007-10 a 2009-03',
        'trigger': 'Colapso hipotecas subprime + quiebra Lehman',
        'sp500': -57, 'hy_spread_peak': 2000, 'ig_spread_peak': 600,
        'vix_peak': 80, 'ust10y_move': -200, 'usdclp_move': +35,
        'copper_move': -65, 'duration_months': 17,
        'conditions': 'Housing bubble, leverage extremo, CDO/MBS sin regulación',
    },
    {
        'name': 'COVID-19 (Pandemia)',
        'period': '2020-02 a 2020-03',
        'trigger': 'Lockdowns globales + shock demanda',
        'sp500': -34, 'hy_spread_peak': 1100, 'ig_spread_peak': 400,
        'vix_peak': 82, 'ust10y_move': -140, 'usdclp_move': +18,
        'copper_move': -26, 'duration_months': 1.5,
        'conditions': 'Shock exógeno, economía sana pre-crisis, respuesta fiscal masiva',
    },
    {
        'name': 'Taper Tantrum',
        'period': '2013-05 a 2013-09',
        'trigger': 'Bernanke anuncia reducción de QE',
        'sp500': -6, 'hy_spread_peak': 550, 'ig_spread_peak': 160,
        'vix_peak': 21, 'ust10y_move': +130, 'usdclp_move': +12,
        'copper_move': -12, 'duration_months': 4,
        'conditions': 'Recuperación post-GFC, política monetaria acomodaticia',
    },
    {
        'name': 'SVB/Credit Suisse',
        'period': '2023-03',
        'trigger': 'Corrida bancaria SVB + crisis CS',
        'sp500': -8, 'hy_spread_peak': 530, 'ig_spread_peak': 170,
        'vix_peak': 30, 'ust10y_move': -60, 'usdclp_move': +5,
        'copper_move': -5, 'duration_months': 1,
        'conditions': 'Tasas altas, duration losses en carteras bancarias, contagio limitado',
    },
    {
        'name': 'Volmageddon',
        'period': '2018-02',
        'trigger': 'Colapso de estrategias short-vol (XIV)',
        'sp500': -10, 'hy_spread_peak': 380, 'ig_spread_peak': 130,
        'vix_peak': 50, 'ust10y_move': +20, 'usdclp_move': +3,
        'copper_move': -8, 'duration_months': 0.5,
        'conditions': 'VIX en mínimos históricos, apalancamiento en short-vol excesivo',
    },
    {
        'name': 'Shock Energético 2022',
        'period': '2022-01 a 2022-10',
        'trigger': 'Invasión Rusia-Ucrania + crisis gas Europa',
        'sp500': -25, 'hy_spread_peak': 600, 'ig_spread_peak': 180,
        'vix_peak': 36, 'ust10y_move': +230, 'usdclp_move': +20,
        'copper_move': -25, 'duration_months': 10,
        'conditions': 'Inflación post-COVID, tightening agresivo, crisis energética Europa',
    },
    {
        'name': 'Crisis Euro / Deuda Soberana',
        'period': '2011-07 a 2012-07',
        'trigger': 'Grecia/Italia/España — riesgo fragmentación eurozona',
        'sp500': -19, 'hy_spread_peak': 700, 'ig_spread_peak': 250,
        'vix_peak': 45, 'ust10y_move': -100, 'usdclp_move': +15,
        'copper_move': -20, 'duration_months': 12,
        'conditions': 'Austeridad fiscal, sin unión bancaria, Draghi "whatever it takes"',
    },
    {
        'name': 'Q4 2018 (Fed Hawkish)',
        'period': '2018-10 a 2018-12',
        'trigger': 'Fed sube tasas + "autopilot" balance sheet',
        'sp500': -20, 'hy_spread_peak': 530, 'ig_spread_peak': 160,
        'vix_peak': 36, 'ust10y_move': -40, 'usdclp_move': +8,
        'copper_move': -12, 'duration_months': 3,
        'conditions': 'Ciclo tardío, valuaciones estiradas, trade war China',
    },
]


def get_crisis_reference_text() -> str:
    """Generate formatted crisis reference for agent prompts."""
    lines = [
        "## EPISODIOS HISTÓRICOS DE REFERENCIA (datos verificados)",
        "Usa estos episodios para calibrar probabilidades y dimensionar impactos.",
        "Para cada analogía, indica SIMILITUDES y DIFERENCIAS con la situación actual.",
        ""
    ]

    for ep in CRISIS_EPISODES:
        lines.append(f"### {ep['name']} ({ep['period']})")
        lines.append(f"Trigger: {ep['trigger']}")
        lines.append(f"Impactos: S&P {ep['sp500']:+d}%, HY spread {ep['hy_spread_peak']}bps, "
                      f"IG {ep['ig_spread_peak']}bps, VIX {ep['vix_peak']}, "
                      f"UST10Y {ep['ust10y_move']:+d}bps, USD/CLP {ep['usdclp_move']:+d}%, "
                      f"Cobre {ep['copper_move']:+d}%")
        lines.append(f"Duración: {ep['duration_months']} meses")
        lines.append(f"Condiciones: {ep['conditions']}")
        lines.append("")

    return "\n".join(lines)
