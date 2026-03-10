# -*- coding: utf-8 -*-
"""
Greybark Research - Daily Report Parser
========================================

Parsea los reportes diarios HTML y extrae información estructurada
para alimentar al AI Council.

Uso:
    parser = DailyReportParser()
    summary = parser.get_monthly_summary(days=30)
"""

import os
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup
import json


# Rutas de reportes: se busca en AMBAS carpetas y se combinan resultados
_LOCAL_HTML_OUT = Path(__file__).resolve().parent / "html_out"
_LEGACY_HTML_OUT = Path.home() / "OneDrive/Documentos/proyectos/archivo_reportes/html"
_ALL_REPORT_PATHS = [p for p in [_LOCAL_HTML_OUT, _LEGACY_HTML_OUT] if p.exists()]
DEFAULT_REPORTS_PATH = os.environ.get(
    'DAILY_REPORTS_PATH',
    str(_ALL_REPORT_PATHS[0]) if _ALL_REPORT_PATHS else str(_LOCAL_HTML_OUT)
)


class DailyReportParser:
    """Parser de reportes diarios HTML de Greybark Research."""

    def __init__(self, reports_path: str = DEFAULT_REPORTS_PATH):
        self.reports_path = Path(reports_path)
        # Search paths: explicit path + all known paths (deduplicated)
        self._search_paths = []
        seen = set()
        for p in [self.reports_path] + _ALL_REPORT_PATHS:
            rp = p.resolve()
            if rp not in seen and rp.exists():
                seen.add(rp)
                self._search_paths.append(p)

    def list_reports(self, report_type: str = "no_finanzas", days: int = 30) -> List[Path]:
        """
        Lista reportes disponibles filtrados por tipo y fecha.
        Busca en TODAS las rutas conocidas y combina resultados.

        Args:
            report_type: "no_finanzas" o "finanzas"
            days: Número de días hacia atrás

        Returns:
            Lista de paths a reportes HTML ordenados por fecha
        """
        pattern = f"*_{report_type}_*.html"
        cutoff_date = datetime.now() - timedelta(days=days)

        # Collect from all search paths, deduplicate by filename
        seen_names = set()
        reports = []
        for search_path in self._search_paths:
            for f in search_path.glob(pattern):
                if f.name in seen_names:
                    continue
                seen_names.add(f.name)
                # Extraer fecha del nombre: daily_report_PM_no_finanzas_2026-02-03.html
                match = re.search(r'(\d{4}-\d{2}-\d{2})', f.name)
                if match:
                    date_str = match.group(1)
                    try:
                        file_date = datetime.strptime(date_str, '%Y-%m-%d')
                        if file_date >= cutoff_date:
                            reports.append((file_date, f))
                    except ValueError:
                        continue

        # Ordenar por fecha
        reports.sort(key=lambda x: x[0])
        return [r[1] for r in reports]

    def parse_report(self, file_path: Path) -> Dict[str, Any]:
        """
        Parsea un reporte HTML y extrae secciones clave.

        Returns:
            Dict con:
                - date: fecha del reporte
                - type: AM o PM
                - resumen_ejecutivo: lista de bullets
                - economia: texto
                - politica_geopolitica: texto
                - ia_tecnologia: texto
                - chile_latam: texto
                - mercados: texto
                - sentimiento: texto
                - idea_tactica: texto
                - market_data: dict con datos de mercado
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            html = f.read()

        soup = BeautifulSoup(html, 'html.parser')

        # Extraer fecha y tipo del título
        title = soup.find('title')
        title_text = title.text if title else file_path.name

        report_type = "PM" if "PM" in title_text else "AM"

        # Extraer fecha
        match = re.search(r'(\d{4}-\d{2}-\d{2})', file_path.name)
        date_str = match.group(1) if match else "unknown"

        # Extraer secciones por h2
        sections = {}
        current_section = None
        current_content = []

        for elem in soup.find_all(['h2', 'p', 'ul', 'table']):
            if elem.name == 'h2':
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = self._normalize_section_name(elem.get_text(strip=True))
                current_content = []
            elif current_section:
                if elem.name == 'p':
                    current_content.append(elem.get_text(strip=True))
                elif elem.name == 'ul':
                    for li in elem.find_all('li'):
                        current_content.append(f"- {li.get_text(strip=True)}")

        if current_section:
            sections[current_section] = '\n'.join(current_content)

        # Extraer datos de mercado de las tablas
        market_data = self._extract_market_data(soup)

        return {
            'date': date_str,
            'type': report_type,
            'file': file_path.name,
            'sections': sections,
            'market_data': market_data,
            'resumen_ejecutivo': sections.get('resumen_ejecutivo', ''),
            'economia': sections.get('economia', ''),
            'politica_geopolitica': sections.get('politica_y_geopolitica', sections.get('politica_geopolitica', '')),
            'ia_tecnologia': sections.get('inteligencia_artificial_y_tecnologia', sections.get('ia_tecnologia', '')),
            'chile_latam': sections.get('chile_y_latam', sections.get('chile_latam', '')),
            'mercados': sections.get('mercados_por_activo', sections.get('mercados', '')),
            'sentimiento': sections.get('sentimiento_y_volatilidad', sections.get('sentimiento', '')),
            'idea_tactica': sections.get('idea_tactica', '')
        }

    def _normalize_section_name(self, name: str) -> str:
        """Normaliza nombre de sección para consistencia."""
        name = name.lower().strip()
        name = re.sub(r'[^a-záéíóúñ\s]', '', name)
        name = re.sub(r'\s+', '_', name)
        return name

    def _extract_market_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extrae datos de mercado de las tablas."""
        data = {}

        # Buscar tabla de índices
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True)
                    val = cells[1].get_text(strip=True)
                    if key and val and key not in ['ÍNDICE', 'INSTRUMENTO', 'COMMODITY', 'PAR']:
                        data[key] = val

        return data

    def get_monthly_summary(self, days: int = 30, report_type: str = "no_finanzas") -> Dict[str, Any]:
        """
        Genera un resumen consolidado de los últimos N días.

        Args:
            days: Número de días a consolidar
            report_type: Tipo de reporte a usar

        Returns:
            Dict con resumen estructurado para el AI Council
        """
        reports = self.list_reports(report_type=report_type, days=days)

        if not reports:
            return {
                'period': f"Últimos {days} días",
                'reports_count': 0,
                'error': 'No se encontraron reportes'
            }

        parsed_reports = []
        ideas_tacticas = []
        temas_recurrentes = {}

        for report_path in reports:
            try:
                parsed = self.parse_report(report_path)
                parsed_reports.append(parsed)

                # Acumular ideas tácticas
                if parsed.get('idea_tactica'):
                    ideas_tacticas.append({
                        'date': parsed['date'],
                        'idea': parsed['idea_tactica'][:500]  # Limitar longitud
                    })

                # Detectar temas recurrentes en resumen ejecutivo
                resumen = parsed.get('resumen_ejecutivo', '')
                for tema in self._extract_themes(resumen):
                    temas_recurrentes[tema] = temas_recurrentes.get(tema, 0) + 1

            except Exception as e:
                continue

        # Ordenar temas por frecuencia
        temas_top = sorted(temas_recurrentes.items(), key=lambda x: x[1], reverse=True)[:10]

        # Obtener últimos 5 reportes completos para contexto
        ultimos_reportes = []
        for p in parsed_reports[-5:]:
            ultimos_reportes.append({
                'date': p['date'],
                'type': p['type'],
                'resumen': p.get('resumen_ejecutivo', '')[:1000],
                'idea_tactica': p.get('idea_tactica', '')[:300]
            })

        return {
            'period': f"{parsed_reports[0]['date']} a {parsed_reports[-1]['date']}" if parsed_reports else "N/A",
            'reports_count': len(parsed_reports),
            'temas_recurrentes': temas_top,
            'ideas_tacticas_recientes': ideas_tacticas[-10:],  # Últimas 10 ideas
            'ultimos_reportes': ultimos_reportes,
            'market_snapshot': parsed_reports[-1].get('market_data', {}) if parsed_reports else {}
        }

    def _extract_themes(self, text: str) -> List[str]:
        """Extrae temas clave de un texto."""
        themes = []

        # Patrones de temas importantes
        patterns = [
            r'(fed|tasas|inflación|recesión)',
            r'(china|cobre|commodities)',
            r'(tech|nvidia|ai|inteligencia artificial)',
            r'(chile|ipsa|clp|peso)',
            r'(geopolítica|guerra|aranceles|trump)',
            r'(earnings|resultados|utilidades)',
            r'(volatilidad|vix|riesgo)'
        ]

        text_lower = text.lower()
        for pattern in patterns:
            if re.search(pattern, text_lower):
                match = re.search(pattern, text_lower)
                themes.append(match.group(1))

        return themes

    def format_for_council(self, summary: Dict) -> str:
        """
        Formatea el resumen en texto para incluir en el prompt del Council.

        Args:
            summary: Output de get_monthly_summary()

        Returns:
            Texto formateado para incluir en prompt
        """
        lines = []
        lines.append(f"## RESUMEN DE REPORTES DIARIOS ({summary['reports_count']} reportes)")
        lines.append(f"Período: {summary['period']}")
        lines.append("")

        # Temas recurrentes
        lines.append("### TEMAS RECURRENTES DEL MES")
        for tema, count in summary.get('temas_recurrentes', []):
            lines.append(f"- {tema}: mencionado {count} veces")
        lines.append("")

        # Ideas tácticas recientes
        lines.append("### IDEAS TÁCTICAS RECIENTES")
        for idea in summary.get('ideas_tacticas_recientes', [])[-5:]:
            lines.append(f"- [{idea['date']}] {idea['idea'][:200]}...")
        lines.append("")

        # Últimos reportes
        lines.append("### ÚLTIMOS REPORTES")
        for r in summary.get('ultimos_reportes', []):
            lines.append(f"\n**{r['date']} ({r['type']})**")
            lines.append(r['resumen'][:500])

        return '\n'.join(lines)


def main():
    """Test del parser."""
    parser = DailyReportParser()

    print("=" * 60)
    print("DAILY REPORT PARSER - TEST")
    print("=" * 60)

    # Listar reportes disponibles
    reports = parser.list_reports(days=30)
    print(f"\nReportes encontrados: {len(reports)}")

    if reports:
        print(f"Más reciente: {reports[-1].name}")

        # Parsear último reporte
        print("\n--- Parseando último reporte ---")
        parsed = parser.parse_report(reports[-1])
        print(f"Fecha: {parsed['date']}")
        print(f"Tipo: {parsed['type']}")
        print(f"Secciones: {list(parsed['sections'].keys())}")

        # Generar resumen mensual
        print("\n--- Resumen mensual ---")
        summary = parser.get_monthly_summary(days=30)
        print(f"Reportes: {summary['reports_count']}")
        print(f"Período: {summary['period']}")
        print(f"Temas top: {summary['temas_recurrentes'][:5]}")

        # Formato para Council
        print("\n--- Formato para Council ---")
        formatted = parser.format_for_council(summary)
        print(formatted[:2000])


if __name__ == "__main__":
    main()
