# -*- coding: utf-8 -*-
"""
Greybark Research — Report Enhancements (Tier 2)
===================================================

Goldman Sachs-quality additions to reports:
1. "Qué Cambió" — structured Previous → Current table with arrows
2. "Qué Está Priceado" — market-implied vs our view
3. Cross-asset implications matrix

These functions return HTML snippets injected by renderers.
"""

from typing import Dict, Optional


def generate_what_changed_html(current: Dict, previous: Dict) -> str:
    """Generate "Qué Cambió vs Reporte Anterior" structured table.

    Args:
        current: dict of metric_id → {'view': 'OW', 'level': '4.35%', ...}
        previous: dict of metric_id → {'view': 'N', 'level': '4.50%', ...}

    Returns HTML table with arrows showing changes.
    """
    if not current:
        return ''

    rows = []
    for metric_id, curr in current.items():
        prev = previous.get(metric_id, {})
        curr_view = curr.get('view', '')
        prev_view = prev.get('view', '')
        curr_level = curr.get('level', '')
        prev_level = prev.get('level', '')
        label = curr.get('label', metric_id)

        # Determine change arrow
        if curr_view != prev_view and prev_view:
            arrow = '&#9650;' if _view_score(curr_view) > _view_score(prev_view) else '&#9660;'
            change_class = 'change-up' if arrow == '&#9650;' else 'change-down'
            change_text = f'{prev_view} → {curr_view}'
        elif not prev_view:
            arrow = ''
            change_class = 'change-new'
            change_text = 'Nuevo'
        else:
            arrow = '→'
            change_class = 'change-flat'
            change_text = 'Sin cambio'

        rows.append(f'''<tr>
            <td>{label}</td>
            <td class="center">{prev_view or '—'}</td>
            <td class="center"><strong>{curr_view}</strong></td>
            <td class="center {change_class}">{arrow} {change_text}</td>
            <td class="center" style="font-size:9pt;color:#718096;">{curr_level}</td>
        </tr>''')

    if not rows:
        return ''

    return f'''
    <div style="margin: 20px 0; page-break-inside: avoid;">
        <h3 style="color: var(--accent); margin-bottom: 10px;">Qué Cambió vs Reporte Anterior</h3>
        <table style="width:100%; border-collapse:collapse; font-size:10pt;">
            <thead>
                <tr style="background:#f7f7f7; border-bottom:2px solid #e0e0e0;">
                    <th style="text-align:left; padding:8px;">Clase de Activo</th>
                    <th style="text-align:center; padding:8px;">Anterior</th>
                    <th style="text-align:center; padding:8px;">Actual</th>
                    <th style="text-align:center; padding:8px;">Cambio</th>
                    <th style="text-align:center; padding:8px;">Nivel</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
        <p style="font-size:8pt; color:#a0aec0; margin-top:5px;">
            Solo se muestran cambios de posición. &#9650; = upgrade, &#9660; = downgrade, → = sin cambio.
        </p>
    </div>
    '''


def generate_whats_priced_in_html(rate_data: Dict, council_views: Dict = None) -> str:
    """Generate "Qué Está Priceado" section.

    Shows what the market is discounting vs our council view.
    """
    rows = []

    # Fed rate cuts priced
    fed_current = rate_data.get('fed_funds_current')
    fed_terminal = rate_data.get('fed_terminal')
    fed_cuts_mkt = rate_data.get('market_cuts_priced')
    fed_cuts_grb = council_views.get('fed_cuts_expected') if council_views else None

    if fed_current and fed_terminal:
        implied_cuts = round((fed_current - fed_terminal) / 0.25)
        market_view = f'{implied_cuts} cortes ({fed_current:.2f}% → {fed_terminal:.2f}%)'
        our_view = f'{fed_cuts_grb} cortes' if fed_cuts_grb else 'Ver council'
        delta = ''
        if fed_cuts_grb and implied_cuts != fed_cuts_grb:
            if implied_cuts > fed_cuts_grb:
                delta = f'Mercado más dovish ({implied_cuts} vs {fed_cuts_grb})'
            else:
                delta = f'Mercado más hawkish ({implied_cuts} vs {fed_cuts_grb})'

        rows.append({
            'metric': 'Recortes Fed 12m',
            'market': market_view,
            'greybark': our_view,
            'delta': delta,
        })

    # TPM Chile
    tpm_current = rate_data.get('tpm_current')
    tpm_terminal = rate_data.get('tpm_terminal')
    if tpm_current and tpm_terminal:
        implied = round((tpm_current - tpm_terminal) / 0.25)
        direction = 'recortes' if implied > 0 else 'alzas' if implied < 0 else 'sin cambio'
        rows.append({
            'metric': 'TPM Chile 12m',
            'market': f'{abs(implied)} {direction} ({tpm_current:.2f}% → {tpm_terminal:.2f}%)',
            'greybark': council_views.get('tpm_path', 'Ver council') if council_views else 'Ver council',
            'delta': '',
        })

    # Equity implied return
    sp500_pe = rate_data.get('sp500_pe')
    if sp500_pe:
        earnings_yield = round(1 / sp500_pe * 100, 1)
        rows.append({
            'metric': 'S&P 500 Earnings Yield',
            'market': f'{earnings_yield:.1f}% (P/E {sp500_pe:.1f}x)',
            'greybark': council_views.get('sp500_view', 'Ver council') if council_views else 'Ver council',
            'delta': f'Earnings yield {earnings_yield:.1f}% vs UST 10Y {rate_data.get("ust_10y", "?")}%' if rate_data.get('ust_10y') else '',
        })

    if not rows:
        return ''

    table_rows = ''
    for r in rows:
        delta_style = 'color:#c53030;' if 'hawkish' in r['delta'].lower() else ('color:#276749;' if 'dovish' in r['delta'].lower() else 'color:#718096;')
        table_rows += f'''<tr>
            <td style="font-weight:600;">{r['metric']}</td>
            <td>{r['market']}</td>
            <td>{r['greybark']}</td>
            <td style="font-size:9pt; {delta_style}">{r['delta']}</td>
        </tr>'''

    return f'''
    <div style="margin: 20px 0; padding: 15px; background: #f7fafc; border-radius: 8px; border: 1px solid #e2e8f0; page-break-inside: avoid;">
        <h3 style="color: var(--accent); margin: 0 0 12px;">Qué Está Priceado vs Nuestra Visión</h3>
        <table style="width:100%; border-collapse:collapse; font-size:10pt;">
            <thead>
                <tr style="border-bottom:2px solid #e0e0e0;">
                    <th style="text-align:left; padding:6px;">Métrica</th>
                    <th style="text-align:left; padding:6px;">Mercado Pricea</th>
                    <th style="text-align:left; padding:6px;">Greybark</th>
                    <th style="text-align:left; padding:6px;">Delta</th>
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>
    </div>
    '''


def generate_cross_asset_matrix_html(views: Dict) -> str:
    """Generate cross-asset implications matrix.

    "If our view is right → equities X, bonds Y, FX Z, commodities W"
    """
    if not views:
        return ''

    scenario = views.get('base_scenario', 'Escenario base')
    implications = views.get('implications', {})

    if not implications:
        return ''

    rows = ''
    icons = {
        'positive': '&#9650;', 'negative': '&#9660;', 'neutral': '→',
        'up': '&#9650;', 'down': '&#9660;', 'flat': '→',
    }

    for asset_class, impl in implications.items():
        direction = impl.get('direction', 'neutral')
        icon = icons.get(direction, '→')
        color = '#276749' if direction in ('positive', 'up') else ('#c53030' if direction in ('negative', 'down') else '#718096')
        rationale = impl.get('rationale', '')

        rows += f'''<tr>
            <td style="font-weight:600;">{asset_class}</td>
            <td style="text-align:center; color:{color}; font-size:14pt;">{icon}</td>
            <td style="font-size:9pt;">{rationale}</td>
        </tr>'''

    return f'''
    <div style="margin: 20px 0; page-break-inside: avoid;">
        <h3 style="color: var(--accent); margin-bottom: 10px;">Si Nuestra Tesis Es Correcta → Implicancias</h3>
        <p style="font-size:9pt; color:#718096; margin-bottom:8px;">Escenario: {scenario}</p>
        <table style="width:100%; border-collapse:collapse; font-size:10pt;">
            <thead>
                <tr style="background:#f7f7f7; border-bottom:2px solid #e0e0e0;">
                    <th style="text-align:left; padding:8px;">Clase de Activo</th>
                    <th style="text-align:center; padding:8px;">Dirección</th>
                    <th style="text-align:left; padding:8px;">Fundamento</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''


def conviction_stars(level: str) -> str:
    """Convert conviction level to stars: ALTA=★★★, MEDIA=★★, BAJA=★."""
    level = (level or '').upper().strip()
    if level in ('ALTA', 'HIGH', '3'):
        return '<span style="color:#dd6b20; font-size:12pt;" title="Alta convicción">★★★</span>'
    elif level in ('MEDIA', 'MEDIUM', '2'):
        return '<span style="color:#dd6b20; font-size:12pt;" title="Media convicción">★★</span>'
    elif level in ('BAJA', 'LOW', '1'):
        return '<span style="color:#dd6b20; font-size:12pt;" title="Baja convicción">★</span>'
    return '<span style="color:#a0aec0; font-size:10pt;">—</span>'


def generate_where_wrong_html(risks: list) -> str:
    """Generate "Dónde Podemos Estar Equivocados" section.

    Each risk has a falsifiable condition with a quantified trigger.
    Bridgewater-style pre-mortem analysis.

    Args:
        risks: list of dicts with 'condition', 'trigger', 'impact', 'probability'
    """
    if not risks:
        return ''

    rows = ''
    for r in risks:
        prob = r.get('probability', '')
        prob_color = '#c53030' if '>' in str(prob) and any(c.isdigit() for c in str(prob)) else '#718096'

        rows += f'''
        <div style="padding: 12px; border-left: 3px solid #c53030; margin-bottom: 10px; background: #fff5f5; border-radius: 0 6px 6px 0;">
            <div style="display: flex; justify-content: space-between; align-items: baseline;">
                <strong style="color: #2d3748;">{r.get('condition', '')}</strong>
                <span style="font-size: 9pt; color: {prob_color};">Prob: {prob}</span>
            </div>
            <p style="font-size: 9pt; color: #4a5568; margin: 6px 0 0;">
                <strong>Trigger:</strong> {r.get('trigger', '')}
                <br><strong>Impacto:</strong> {r.get('impact', '')}
            </p>
        </div>'''

    return f'''
    <div style="margin: 20px 0; page-break-inside: avoid;">
        <h3 style="color: #c53030; margin-bottom: 12px;">Dónde Podemos Estar Equivocados</h3>
        <p style="font-size: 9pt; color: #718096; margin-bottom: 10px;">
            Condiciones falsificables que invalidarían nuestra tesis. Si se cumplen, revisamos posicionamiento.
        </p>
        {rows}
    </div>
    '''


def generate_tema_central_html(themes: dict, analyst_calls: list = None,
                                variant: str = 'full') -> str:
    """Generate "Tema Central del Mes" section from intelligence digest.

    Identifies the dominant theme of the period and builds a rich narrative
    with evolution, analyst consensus, and implications.

    Args:
        themes: dict from intelligence_digest (theme_id → {category, trend, report_days, recent_contexts})
        analyst_calls: list of analyst call dicts (optional)
        variant: 'full' (for Macro/AA) or 'compact' (for RV/RF)
    """
    if not themes:
        return ''

    # Find dominant theme (most report_days, prefer 'creciente' trend)
    ranked = sorted(
        themes.items(),
        key=lambda x: (
            x[1].get('report_days', 0) * (1.5 if x[1].get('trend') == 'creciente' else 1.0),
        ),
        reverse=True
    )

    if not ranked:
        return ''

    top_id, top = ranked[0]
    category = top.get('category', '')
    trend = top.get('trend', 'estable')
    report_days = top.get('report_days', 0)
    contexts = top.get('recent_contexts', [])

    # Trend icon
    trend_icons = {'creciente': '&#9650;', 'decreciente': '&#9660;', 'estable': '→', 'nuevo': '&#9733;'}
    trend_colors = {'creciente': '#c53030', 'decreciente': '#276749', 'estable': '#718096', 'nuevo': '#dd6b20'}
    trend_icon = trend_icons.get(trend, '→')
    trend_color = trend_colors.get(trend, '#718096')

    # Format title from theme_id
    title = top_id.replace('_', ' ').title()

    # Build context bullets
    context_html = ''
    for ctx in contexts[:4]:
        context_html += f'<li style="margin-bottom:4px; font-size:9pt; color:#4a5568;">{ctx}</li>'

    # Analyst consensus on this theme (if available)
    analyst_html = ''
    if analyst_calls:
        # Filter calls related to this theme's category
        cat_map = {
            'Geopolítica': ['commodities', 'fx', 'renta_variable'],
            'Política Monetaria': ['renta_fija', 'fx'],
            'Inflación': ['renta_fija', 'commodities'],
            'Commodities': ['commodities'],
            'Crecimiento': ['renta_variable', 'macro'],
        }
        relevant_classes = cat_map.get(category, ['macro'])
        relevant_calls = [c for c in analyst_calls
                          if c.get('asset_class', '') in relevant_classes][:5]

        if relevant_calls:
            buy_count = sum(1 for c in relevant_calls if c.get('direction', '').upper() in ('BUY', 'LONG'))
            sell_count = sum(1 for c in relevant_calls if c.get('direction', '').upper() in ('SELL', 'SHORT'))
            consensus = 'Bullish' if buy_count > sell_count else ('Bearish' if sell_count > buy_count else 'Mixto')
            cons_color = '#276749' if consensus == 'Bullish' else ('#c53030' if consensus == 'Bearish' else '#718096')

            top_call = relevant_calls[0]
            analyst_html = f'''
            <div style="margin-top:10px; padding:10px; background:#f7fafc; border-radius:6px; border:1px solid #e2e8f0;">
                <div style="font-size:9pt; font-weight:600; color:#2d3748;">
                    Consenso Analistas: <span style="color:{cons_color};">{consensus}</span>
                    ({buy_count} bullish, {sell_count} bearish de {len(relevant_calls)} calls)
                </div>
                <p style="font-size:9pt; color:#718096; margin:4px 0 0;">
                    Top call: {top_call.get('analyst', '?')} ({top_call.get('firm', '?')}) —
                    {top_call.get('direction', '?')} {top_call.get('asset', '?')}:
                    {top_call.get('thesis', '')[:120]}
                </p>
            </div>'''

    # Secondary themes
    secondary_html = ''
    if len(ranked) > 1 and variant == 'full':
        secondary_items = []
        for tid, t in ranked[1:4]:
            t_trend = trend_icons.get(t.get('trend', 'estable'), '→')
            t_color = trend_colors.get(t.get('trend', 'estable'), '#718096')
            t_title = tid.replace('_', ' ').title()
            secondary_items.append(
                f'<span style="display:inline-block; margin-right:12px; font-size:9pt;">'
                f'<span style="color:{t_color};">{t_trend}</span> {t_title} '
                f'<span style="color:#a0aec0;">({t.get("report_days", 0)}d)</span></span>'
            )
        if secondary_items:
            secondary_html = f'''
            <div style="margin-top:10px; padding-top:8px; border-top:1px solid #e2e8f0;">
                <span style="font-size:8pt; color:#a0aec0; text-transform:uppercase; letter-spacing:0.05em;">Otros temas:</span>
                <div style="margin-top:4px;">{''.join(secondary_items)}</div>
            </div>'''

    # Compact variant (for RV/RF)
    if variant == 'compact':
        return f'''
        <div style="margin:15px 0; padding:12px 16px; border-left:3px solid #dd6b20; background:#fffaf5; border-radius:0 6px 6px 0;">
            <div style="display:flex; align-items:baseline; gap:8px;">
                <span style="font-size:10pt; font-weight:700; color:#2d3748;">Foco del Período:</span>
                <span style="font-size:10pt; color:#4a5568;">{title}</span>
                <span style="color:{trend_color}; font-size:11pt;">{trend_icon}</span>
                <span style="font-size:8pt; color:#a0aec0;">({report_days} días en reportes)</span>
            </div>
            {f'<p style="font-size:9pt; color:#718096; margin:4px 0 0;">{contexts[0][:150]}</p>' if contexts else ''}
        </div>
        '''

    # Full variant (for Macro/AA)
    return f'''
    <div style="margin:20px 0; page-break-inside:avoid;">
        <div style="border-left:4px solid #dd6b20; padding:16px 20px; background:linear-gradient(135deg, #fffaf5 0%, #fff 100%); border-radius:0 8px 8px 0; box-shadow:0 1px 3px rgba(0,0,0,0.06);">
            <div style="display:flex; align-items:baseline; justify-content:space-between; margin-bottom:10px;">
                <div>
                    <p style="font-size:8pt; color:#a0aec0; text-transform:uppercase; letter-spacing:0.08em; margin:0 0 2px;">Foco del Período</p>
                    <h3 style="font-size:14pt; font-weight:700; color:#1a2332; margin:0;">
                        {title}
                        <span style="color:{trend_color}; font-size:14pt; margin-left:6px;">{trend_icon}</span>
                    </h3>
                </div>
                <div style="text-align:right;">
                    <span style="font-size:9pt; color:#718096;">{report_days} días en reportes</span>
                    <br><span style="font-size:8pt; color:#a0aec0;">{category}</span>
                </div>
            </div>

            <ul style="margin:0; padding-left:20px;">
                {context_html}
            </ul>

            {analyst_html}
            {secondary_html}
        </div>
    </div>
    '''


def _view_score(view: str) -> int:
    """Convert view to numeric score for comparison."""
    view = (view or '').upper().strip()
    scores = {'UW': -2, 'SUBPONDERAR': -2, 'N': 0, 'NEUTRAL': 0, 'OW': 2, 'SOBREPONDERAR': 2}
    return scores.get(view, 0)
