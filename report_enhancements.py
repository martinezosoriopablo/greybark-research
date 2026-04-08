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


def generate_copper_sensitivity_html(copper_price: float = None,
                                     usdclp: float = None) -> str:
    """Generate copper sensitivity table for Chile section.

    "$0.10/lb change in copper = X bps fiscal, Y% CLP, Z bps BCP"
    Standard for any serious Chile/LatAm research.
    """
    if not copper_price:
        return ''

    # Empirical sensitivities (documented in Chilean fiscal/macro research)
    # These are approximate and should be updated periodically
    base = copper_price
    sensitivities = [
        {'change': '-$0.50/lb', 'price': f'${base - 0.50:.2f}', 'fiscal': '-80 a -100 bps', 'clp': '+4 a +6%', 'bcp_spread': '+15 a +20 bps', 'color': '#c53030'},
        {'change': '-$0.25/lb', 'price': f'${base - 0.25:.2f}', 'fiscal': '-40 a -50 bps', 'clp': '+2 a +3%', 'bcp_spread': '+8 a +10 bps', 'color': '#dd6b20'},
        {'change': 'Actual', 'price': f'${base:.2f}', 'fiscal': 'Base', 'clp': f'${usdclp:,.0f}' if usdclp else 'Actual', 'bcp_spread': 'Base', 'color': '#2d3748'},
        {'change': '+$0.25/lb', 'price': f'${base + 0.25:.2f}', 'fiscal': '+40 a +50 bps', 'clp': '-2 a -3%', 'bcp_spread': '-5 a -8 bps', 'color': '#276749'},
        {'change': '+$0.50/lb', 'price': f'${base + 0.50:.2f}', 'fiscal': '+80 a +100 bps', 'clp': '-4 a -6%', 'bcp_spread': '-10 a -15 bps', 'color': '#276749'},
    ]

    rows = ''
    for s in sensitivities:
        is_base = s['change'] == 'Actual'
        weight = 'font-weight:700;' if is_base else ''
        bg = 'background:#f7f7f7;' if is_base else ''
        rows += f'''<tr style="{bg}">
            <td style="{weight} color:{s['color']};">{s['change']}</td>
            <td style="{weight}">{s['price']}</td>
            <td style="text-align:center;">{s['fiscal']}</td>
            <td style="text-align:center;">{s['clp']}</td>
            <td style="text-align:center;">{s['bcp_spread']}</td>
        </tr>'''

    return f'''
    <div style="margin:15px 0; page-break-inside:avoid;">
        <h4 style="color:var(--accent); margin-bottom:8px;">Sensibilidad al Cobre (principal exportación de Chile)</h4>
        <table style="width:100%; border-collapse:collapse; font-size:9pt;">
            <thead>
                <tr style="background:#f7f7f7; border-bottom:2px solid #e0e0e0;">
                    <th style="padding:6px; text-align:left;">Cambio</th>
                    <th style="padding:6px; text-align:left;">Precio Cu</th>
                    <th style="padding:6px; text-align:center;">Balance Fiscal</th>
                    <th style="padding:6px; text-align:center;">USD/CLP</th>
                    <th style="padding:6px; text-align:center;">Spread BCP</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
        <p style="font-size:7pt; color:#a0aec0; margin-top:4px;">Sensibilidades aproximadas basadas en elasticidades históricas. Cobre representa ~50% de exportaciones y ~10% de ingresos fiscales de Chile.</p>
    </div>
    '''


def callout_box(text: str, box_type: str = 'info') -> str:
    """Generate a callout box for key information.

    Types: 'key_change' (blue), 'conviction_trade' (green), 'risk_alert' (red), 'info' (gray)
    """
    styles = {
        'key_change': {'border': '#3182ce', 'bg': '#ebf8ff', 'icon': '&#9670;', 'label': 'Cambio Clave'},
        'conviction_trade': {'border': '#276749', 'bg': '#f0fff4', 'icon': '&#9733;', 'label': 'Trade de Convicción'},
        'risk_alert': {'border': '#c53030', 'bg': '#fff5f5', 'icon': '&#9888;', 'label': 'Alerta de Riesgo'},
        'info': {'border': '#718096', 'bg': '#f7fafc', 'icon': '&#8505;', 'label': 'Nota'},
    }
    s = styles.get(box_type, styles['info'])

    return f'''
    <div style="margin:12px 0; padding:12px 16px; border-left:4px solid {s['border']};
                background:{s['bg']}; border-radius:0 6px 6px 0; page-break-inside:avoid;">
        <div style="font-size:8pt; color:{s['border']}; text-transform:uppercase;
                    letter-spacing:0.06em; margin-bottom:4px;">
            {s['icon']} {s['label']}
        </div>
        <p style="font-size:10pt; color:#2d3748; margin:0; line-height:1.5;">{text}</p>
    </div>
    '''


def generate_quant_signal_dashboard_html(signals: dict) -> str:
    """Generate quant signal dashboard — momentum/carry/value/vol per asset class.

    JP Morgan style: compact grid showing quantitative signals with qualitative overlay.

    Args:
        signals: dict of asset_class → {momentum, carry, value, vol_regime, overlay, final_view}
    """
    if not signals:
        return ''

    def _signal_cell(val):
        if val is None:
            return '<td style="text-align:center; color:#a0aec0;">—</td>'
        if isinstance(val, str):
            val_lower = val.lower()
            if val_lower in ('positive', 'bullish', '+', 'ow'):
                return '<td style="text-align:center;"><span style="color:#276749; font-weight:600;">&#10003;</span></td>'
            elif val_lower in ('negative', 'bearish', '-', 'uw'):
                return '<td style="text-align:center;"><span style="color:#c53030; font-weight:600;">&#10007;</span></td>'
            else:
                return '<td style="text-align:center;"><span style="color:#718096;">&#8212;</span></td>'
        return f'<td style="text-align:center; color:#718096;">{val}</td>'

    rows = ''
    for asset, s in signals.items():
        mom = _signal_cell(s.get('momentum'))
        carry = _signal_cell(s.get('carry'))
        value = _signal_cell(s.get('value'))
        vol = _signal_cell(s.get('vol_regime'))
        overlay = s.get('overlay', '')
        final = s.get('final_view', '')

        # Count positive signals
        pos = sum(1 for k in ('momentum', 'carry', 'value', 'vol_regime')
                  if str(s.get(k, '')).lower() in ('positive', 'bullish', '+', 'ow'))
        total = sum(1 for k in ('momentum', 'carry', 'value', 'vol_regime') if s.get(k) is not None)
        score_text = f'{pos}/{total}' if total > 0 else '—'
        score_color = '#276749' if pos >= 3 else ('#c53030' if pos <= 1 and total >= 3 else '#718096')

        rows += f'''<tr>
            <td style="font-weight:600;">{asset}</td>
            {mom}{carry}{value}{vol}
            <td style="text-align:center; color:{score_color}; font-weight:600;">{score_text}</td>
            <td style="font-size:9pt; color:#718096;">{overlay}</td>
        </tr>'''

    return f'''
    <div style="margin:20px 0; page-break-inside:avoid;">
        <h3 style="color:var(--accent); margin-bottom:10px;">Panel de Señales Cuantitativas</h3>
        <p style="font-size:8pt; color:#a0aec0; margin-bottom:8px;">
            &#10003; = señal positiva | &#10007; = señal negativa | &#8212; = neutral.
            Overlay cualitativo puede confirmar o divergir de las señales cuantitativas.
        </p>
        <table style="width:100%; border-collapse:collapse; font-size:10pt;">
            <thead>
                <tr style="background:#f7f7f7; border-bottom:2px solid #e0e0e0;">
                    <th style="text-align:left; padding:6px;">Clase de Activo</th>
                    <th style="text-align:center; padding:6px;">Mom</th>
                    <th style="text-align:center; padding:6px;">Carry</th>
                    <th style="text-align:center; padding:6px;">Value</th>
                    <th style="text-align:center; padding:6px;">Vol</th>
                    <th style="text-align:center; padding:6px;">Score</th>
                    <th style="text-align:left; padding:6px;">Overlay Cualitativo</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''


def generate_zscore_table_html(metrics: list) -> str:
    """Generate z-score table — each variable with level, 5Y avg, z-score.

    Bridgewater style: anything beyond ±1.5σ gets highlighted.

    Args:
        metrics: list of dicts with {name, current, avg_5y, zscore, unit}
    """
    if not metrics:
        return ''

    rows = ''
    for m in metrics:
        z = m.get('zscore')
        current = m.get('current')
        avg = m.get('avg_5y')
        unit = m.get('unit', '')
        name = m.get('name', '')

        # Z-score coloring
        if z is not None:
            if abs(z) > 2.0:
                z_color = '#c53030'
                z_bg = '#fff5f5'
                z_label = 'Extremo'
            elif abs(z) > 1.5:
                z_color = '#dd6b20'
                z_bg = '#fffaf5'
                z_label = 'Elevado'
            elif abs(z) > 1.0:
                z_color = '#718096'
                z_bg = ''
                z_label = ''
            else:
                z_color = '#276749'
                z_bg = ''
                z_label = ''
            z_text = f'{z:+.1f}σ'
        else:
            z_color = '#a0aec0'
            z_bg = ''
            z_text = '—'
            z_label = ''

        current_text = f'{current:.1f}{unit}' if current is not None else '—'
        avg_text = f'{avg:.1f}{unit}' if avg is not None else '—'

        rows += f'''<tr style="{'background:' + z_bg + ';' if z_bg else ''}">
            <td>{name}</td>
            <td style="text-align:center; font-weight:600;">{current_text}</td>
            <td style="text-align:center; color:#718096;">{avg_text}</td>
            <td style="text-align:center; color:{z_color}; font-weight:600;">{z_text}</td>
            <td style="text-align:center; font-size:8pt; color:{z_color};">{z_label}</td>
        </tr>'''

    return f'''
    <div style="margin:20px 0; page-break-inside:avoid;">
        <h3 style="color:var(--accent); margin-bottom:10px;">Indicadores vs Historia (Z-Score 5 Años)</h3>
        <p style="font-size:8pt; color:#a0aec0; margin-bottom:8px;">
            Valores más allá de ±1.5σ están resaltados. Positivo = por encima del promedio.
        </p>
        <table style="width:100%; border-collapse:collapse; font-size:10pt;">
            <thead>
                <tr style="background:#f7f7f7; border-bottom:2px solid #e0e0e0;">
                    <th style="text-align:left; padding:6px;">Indicador</th>
                    <th style="text-align:center; padding:6px;">Actual</th>
                    <th style="text-align:center; padding:6px;">Prom 5A</th>
                    <th style="text-align:center; padding:6px;">Z-Score</th>
                    <th style="text-align:center; padding:6px;"></th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''


def generate_traffic_light_grid_html(views: dict) -> str:
    """Generate traffic-light conviction grid — entire house view on one glance.

    Goldman Sachs style: rows = asset classes, columns = time horizons.
    Each cell colored green (OW) / yellow (N) / red (UW) with conviction stars.

    Args:
        views: dict of asset_class → {tactical: {view, conviction}, strategic: {view, conviction}}
    """
    if not views:
        return ''

    def _cell(v):
        if not v:
            return '<td style="text-align:center; padding:8px; background:#f7f7f7;">—</td>'
        view = (v.get('view', '') or '').upper()
        conv = v.get('conviction', '')

        if view in ('OW', 'SOBREPONDERAR'):
            bg = '#f0fff4'
            border = '#276749'
            text = 'OW'
        elif view in ('UW', 'SUBPONDERAR'):
            bg = '#fff5f5'
            border = '#c53030'
            text = 'UW'
        else:
            bg = '#fffff0'
            border = '#dd6b20'
            text = 'N'

        stars = conviction_stars(conv)
        return (f'<td style="text-align:center; padding:8px 12px; background:{bg}; '
                f'border-left:3px solid {border};">'
                f'<div style="font-weight:700; font-size:11pt;">{text}</div>'
                f'<div>{stars}</div></td>')

    rows = ''
    for asset, horizons in views.items():
        tactical = _cell(horizons.get('tactical'))
        strategic = _cell(horizons.get('strategic'))
        rows += f'''<tr>
            <td style="font-weight:600; padding:8px;">{asset}</td>
            {tactical}
            {strategic}
        </tr>'''

    return f'''
    <div style="margin:20px 0; page-break-inside:avoid;">
        <h3 style="color:var(--accent); margin-bottom:10px;">Visión del Comité — Resumen</h3>
        <table style="width:100%; border-collapse:collapse; font-size:10pt;">
            <thead>
                <tr style="background:#1a1a1a; color:white;">
                    <th style="text-align:left; padding:10px; width:40%;">Clase de Activo</th>
                    <th style="text-align:center; padding:10px; width:30%;">Táctico (1-3m)</th>
                    <th style="text-align:center; padding:10px; width:30%;">Estratégico (6-12m)</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
        <p style="font-size:8pt; color:#a0aec0; margin-top:5px;">
            Verde = Sobreponderar (OW) | Amarillo = Neutral (N) | Rojo = Subponderar (UW).
            Estrellas indican nivel de convicción: ★★★ Alta, ★★ Media, ★ Baja.
        </p>
    </div>
    '''


def generate_pull_quote_html(text: str, attribution: str = 'Comité de Inversiones') -> str:
    """Generate pull quote — key CIO statement in large format.

    Magazine-style editorial element between sections.
    """
    if not text:
        return ''

    return f'''
    <div style="margin:30px 40px; padding:20px 30px; border-left:4px solid #dd6b20;
                background:linear-gradient(135deg, #fffaf5 0%, #fff 100%);
                page-break-inside:avoid;">
        <p style="font-size:14pt; font-style:italic; color:#2d3748; line-height:1.6; margin:0;">
            "{text}"
        </p>
        <p style="font-size:9pt; color:#a0aec0; margin:10px 0 0; text-align:right;">
            — {attribution}, Greybark Research
        </p>
    </div>
    '''


def generate_sparkline_svg(values: list, width: int = 60, height: int = 16,
                           color: str = '#dd6b20') -> str:
    """Generate inline SVG sparkline from a list of values.

    Tiny trend chart for embedding in table cells.
    """
    if not values or len(values) < 3:
        return ''

    # Normalize values to SVG coordinates
    min_v = min(values)
    max_v = max(values)
    v_range = max_v - min_v if max_v != min_v else 1

    points = []
    for i, v in enumerate(values):
        x = (i / (len(values) - 1)) * width
        y = height - ((v - min_v) / v_range) * (height - 2) - 1
        points.append(f'{x:.1f},{y:.1f}')

    polyline = ' '.join(points)

    # Color the last segment based on direction
    last_color = '#276749' if values[-1] > values[-2] else ('#c53030' if values[-1] < values[-2] else color)

    return (f'<svg width="{width}" height="{height}" style="display:inline-block; vertical-align:middle;">'
            f'<polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="1.2" opacity="0.6"/>'
            f'<circle cx="{width}" cy="{height - ((values[-1] - min_v) / v_range) * (height - 2) - 1:.1f}" '
            f'r="2" fill="{last_color}"/>'
            f'</svg>')


def _view_score(view: str) -> int:
    """Convert view to numeric score for comparison."""
    view = (view or '').upper().strip()
    scores = {'UW': -2, 'SUBPONDERAR': -2, 'N': 0, 'NEUTRAL': 0, 'OW': 2, 'SOBREPONDERAR': 2}
    return scores.get(view, 0)
