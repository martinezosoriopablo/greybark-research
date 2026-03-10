# -*- coding: utf-8 -*-
"""
Post-procesador HTML que elimina todo rastro de "N/D" de los reportes finales.

Estrategia:
1. Elimina filas <tr> donde TODOS los campos de valor son "N/D"
2. Reemplaza "N/D" sueltos con "-" (guión)
3. Elimina bloques <li> que solo contienen "N/D"
4. Limpia texto narrativo con "N/D"

Se llama desde cada renderer justo antes de escribir el HTML al archivo.
"""
import re


def clean_nd(html: str) -> str:
    """Remove all N/D occurrences from final HTML output.

    Args:
        html: The rendered HTML string

    Returns:
        Cleaned HTML with zero 'N/D' strings
    """
    # Pass 1: Remove <tr> rows where ALL value cells are N/D or empty
    html = _remove_nd_rows(html)

    # Pass 2: Remove <li> items that are just N/D
    html = _remove_nd_list_items(html)

    # Pass 3: Clean narrative/text blocks with N/D
    html = _clean_nd_narratives(html)

    # Pass 4: Replace any remaining bare N/D with dash
    html = _replace_remaining_nd(html)

    return html


def _remove_nd_rows(html: str) -> str:
    """Remove table rows where all value cells contain only N/D."""

    def check_row(match):
        row = match.group(0)
        # Skip header rows
        if '<th' in row:
            return row
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        if len(cells) <= 1:
            return row
        # First cell is label, rest are values
        value_cells = cells[1:]
        nd_or_empty = 0
        for cell in value_cells:
            text = re.sub(r'<[^>]+>', '', cell).strip()
            if text in ('N/D', 'N/D\xa0', '') or text.startswith('N/D —') or text.startswith('N/D —'):
                nd_or_empty += 1
        if nd_or_empty == len(value_cells):
            return ''  # Remove entire row
        return row

    return re.sub(r'<tr[^>]*>.*?</tr>', check_row, html, flags=re.DOTALL)


def _remove_nd_list_items(html: str) -> str:
    """Remove <li> items that only contain N/D."""

    def check_li(match):
        li = match.group(0)
        text = re.sub(r'<[^>]+>', '', li).strip()
        if text in ('N/D', '') or text.startswith('N/D —') or text.startswith('N/D —'):
            return ''
        return li

    return re.sub(r'<li[^>]*>.*?</li>', check_li, html, flags=re.DOTALL)


def _clean_nd_narratives(html: str) -> str:
    """Clean N/D from narrative text blocks."""
    # Remove paragraphs that are entirely N/D
    def check_p(match):
        p = match.group(0)
        text = re.sub(r'<[^>]+>', '', p).strip()
        if text in ('N/D', '') or text.startswith('N/D —') or text.startswith('N/D —'):
            return ''
        return p

    html = re.sub(r'<p[^>]*>.*?</p>', check_p, html, flags=re.DOTALL)

    # Remove divs that only contain N/D
    def check_div_short(match):
        div = match.group(0)
        # Only match short divs (narrative boxes, not large containers)
        if len(div) > 500:
            return div
        text = re.sub(r'<[^>]+>', '', div).strip()
        if text in ('N/D', '') or text.startswith('N/D —'):
            return ''
        return div

    html = re.sub(r'<div class="(?:narrative|summary|intro|comment)[^"]*"[^>]*>.*?</div>',
                  check_div_short, html, flags=re.DOTALL)

    return html


def _protect_base64_nd(html: str) -> str:
    """Replace N/D inside <img> tags with placeholder using string ops.

    Regex fails on 181K+ char base64 image tags, so we split manually.
    """
    parts = html.split('<img ')
    if len(parts) <= 1:
        return html
    result = [parts[0]]
    for part in parts[1:]:
        # Find closing > of the <img> tag
        close = part.find('>')
        if close == -1:
            result.append('<img ' + part)
            continue
        img_content = part[:close + 1]
        rest = part[close + 1:]
        # Only protect if it looks like base64 data
        if 'base64' in img_content or 'data:image' in img_content:
            img_content = img_content.replace('N/D', 'N_D_B64')
        result.append('<img ' + img_content + rest)
    return ''.join(result)


def _replace_remaining_nd(html: str) -> str:
    """Replace any remaining N/D with a dash.

    Carefully avoids base64 image data which may contain 'N/D' as
    part of the encoded binary string.
    """
    # Protect base64 data by temporarily replacing N/D within <img> tags.
    # Regex fails on 181K+ char tags, so we use string splitting instead.
    html = _protect_base64_nd(html)

    # N/D with explanatory suffix → just dash
    html = re.sub(r'N/D\s*[—–-]\s*[^<]*', '-', html)
    # Bare N/D between tags
    html = re.sub(r'>(\s*)N/D(\s*)<', r'>\1-\2<', html)
    # N/D in attribute values (data attributes, alt text)
    html = re.sub(r'="N/D"', '="-"', html)
    # N/D followed by </span> or </td> (inline at end of element)
    html = re.sub(r'N/D\s*</(?:span|td|div|p)', lambda m: '-' + m.group(0)[3:], html)
    # N/D inline in text: "Label: N/D" or "Label: N/D," or "Label: N/D."
    html = re.sub(r':\s*N/D([,.\s<])', r': -\1', html)
    # Any remaining standalone N/D in text (not inside attribute values or base64)
    html = re.sub(r'(?<=>)([^<]*?)N/D([^<]*?)(?=<)',
                  lambda m: m.group(0).replace('N/D', '-'), html)

    # Restore base64 data
    html = html.replace('N_D_B64', 'N/D')

    return html
