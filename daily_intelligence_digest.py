# -*- coding: utf-8 -*-
"""
Greybark Research - Daily Intelligence Digest
===============================================

Procesa los reportes diarios AM/PM y genera un digest de inteligencia
estructurado para alimentar al AI Council.

A diferencia del daily_report_parser (que extrae datos crudos), este módulo
ANALIZA las narrativas: identifica temas dominantes con contexto, rastrea
evolución de sentimiento, categoriza ideas tácticas, y detecta cambios
de narrativa entre semanas.

Los datos numéricos de mercado NO se extraen de los reportes — esos vienen
de BCCh, FRED y AlphaVantage APIs. Aquí solo importa la NARRATIVA.

Uso:
    digest = DailyIntelligenceDigest()
    result = digest.generate()
    formatted = digest.format_for_council(result)
"""

import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from daily_report_parser import DailyReportParser


# =========================================================================
# TAXONOMÍA DE TEMAS
# =========================================================================
# Cada tema tiene: categoría, palabras clave (regex), y peso de relevancia.
# Cuando se detecta un match, se extrae la oración completa como contexto.

THEME_TAXONOMY = {
    # --- POLÍTICA MONETARIA ---
    'fed_política': {
        'category': 'Política Monetaria',
        'patterns': [
            r'(?:fed|federal reserve|powell|fomc)',
            r'(?:tasas?\s+de\s+interés|rate\s+cut|rate\s+hike)',
            r'(?:recorte|alza|pausa)\s+(?:de\s+)?tasas?',
        ],
        'weight': 3,
    },
    'ecb_política': {
        'category': 'Política Monetaria',
        'patterns': [
            r'(?:ecb|bce|lagarde|banco\s+central\s+europeo)',
        ],
        'weight': 2,
    },
    'pboc_política': {
        'category': 'Política Monetaria',
        'patterns': [
            r'(?:pboc|banco\s+central.*china|rrr|lpr)',
        ],
        'weight': 2,
    },
    'bcch_política': {
        'category': 'Política Monetaria',
        'patterns': [
            r'(?:banco\s+central\s+de\s+chile|bcch|tpm|rosanna\s+costa)',
        ],
        'weight': 2,
    },

    # --- INFLACIÓN ---
    'inflación_usa': {
        'category': 'Inflación',
        'patterns': [
            r'(?:inflaci[oó]n|cpi|pce|ipc).*(?:usa|estados\s+unidos|eeuu|americano)',
            r'(?:usa|estados\s+unidos|eeuu).*(?:inflaci[oó]n|cpi|pce|ipc)',
        ],
        'weight': 3,
    },
    'inflación_global': {
        'category': 'Inflación',
        'patterns': [
            r'(?:inflaci[oó]n|deflaci[oó]n|desinflaci[oó]n)',
        ],
        'weight': 2,
    },

    # --- CRECIMIENTO ---
    'recesión_riesgo': {
        'category': 'Crecimiento',
        'patterns': [
            r'(?:recesi[oó]n|desaceleraci[oó]n|aterrizaje\s+suave|soft\s+landing|hard\s+landing)',
        ],
        'weight': 3,
    },
    'empleo_usa': {
        'category': 'Crecimiento',
        'patterns': [
            r'(?:empleo|desempleo|nfp|nonfarm|payrolls|jolts|mercado\s+laboral)',
        ],
        'weight': 2,
    },
    'gdp_crecimiento': {
        'category': 'Crecimiento',
        'patterns': [
            r'(?:gdp|pib|crecimiento\s+econ[oó]mico)',
        ],
        'weight': 2,
    },

    # --- GEOPOLÍTICA ---
    'aranceles_trump': {
        'category': 'Geopolítica',
        'patterns': [
            r'(?:arancel|tariff|trump.*comerci|guerra\s+comercial|trade\s+war)',
        ],
        'weight': 3,
    },
    'china_geopolítica': {
        'category': 'Geopolítica',
        'patterns': [
            r'(?:china|xi\s+jinping|beijing|pek[ií]n).*(?:tensión|sanciones|desacoplamiento|decoupling)',
            r'(?:tensión|sanciones|desacoplamiento).*(?:china|beijing)',
        ],
        'weight': 2,
    },
    'geopolítica_general': {
        'category': 'Geopolítica',
        'patterns': [
            r'(?:geopol[ií]tic|conflicto|guerra|sanciones|tensión\s+geopolítica)',
        ],
        'weight': 1,
    },

    # --- COMMODITIES ---
    'cobre': {
        'category': 'Commodities',
        'patterns': [
            r'\bcobre\b|\bcopper\b',
        ],
        'weight': 2,
    },
    'petróleo': {
        'category': 'Commodities',
        'patterns': [
            r'(?:petr[oó]leo|wti|brent|opep|opec|crudo)',
        ],
        'weight': 2,
    },
    'oro': {
        'category': 'Commodities',
        'patterns': [
            r'\boro\b|\bgold\b(?!man)',
        ],
        'weight': 2,
    },

    # --- TECNOLOGÍA / IA ---
    'inteligencia_artificial': {
        'category': 'Tecnología',
        'patterns': [
            r'(?:inteligencia\s+artificial|\bia\b|ai\b|machine\s+learning|deep\s+learning)',
            r'(?:chatgpt|claude|gemini|openai|anthropic|nvidia.*ai)',
        ],
        'weight': 2,
    },
    'tech_earnings': {
        'category': 'Tecnología',
        'patterns': [
            r'(?:nvidia|apple|microsoft|google|alphabet|meta|amazon|tesla).*(?:result|earning|reporte|utilidad)',
            r'(?:result|earning).*(?:nvidia|apple|microsoft|google|meta|amazon|tesla)',
            r'(?:mag\s*7|magnífic[oa]s?\s+7|big\s+tech)',
        ],
        'weight': 2,
    },

    # --- CHILE ---
    'chile_macro': {
        'category': 'Chile',
        'patterns': [
            r'(?:chile|ipsa|peso\s+chileno|clp|imacec)',
        ],
        'weight': 2,
    },
    'chile_político': {
        'category': 'Chile',
        'patterns': [
            r'(?:boric|constitución|reforma\s+tributaria|reforma\s+pensiones|congreso\s+chile)',
        ],
        'weight': 1,
    },

    # --- RIESGO / VOLATILIDAD ---
    'volatilidad': {
        'category': 'Riesgo',
        'patterns': [
            r'(?:vix|volatilidad|risk[\s-]?off|risk[\s-]?on|miedo|pánico)',
        ],
        'weight': 2,
    },
    'crédito_riesgo': {
        'category': 'Riesgo',
        'patterns': [
            r'(?:spread.*crédito|high\s+yield|default|quiebra|bancarrota)',
        ],
        'weight': 2,
    },

    # --- EARNINGS ---
    'earnings_season': {
        'category': 'Earnings',
        'patterns': [
            r'(?:earning|resultado|utilidad|guidance|reporte\s+trimestral|q[1-4])',
        ],
        'weight': 1,
    },

    # --- RENTA FIJA ---
    'curva_rendimiento': {
        'category': 'Renta Fija',
        'patterns': [
            r'(?:curva.*rendimiento|yield\s+curve|treasury|bonos?\s+(?:10|2|30)\s*(?:y|año))',
            r'(?:inversión.*curva|curva.*invertida|steepening|flattening)',
        ],
        'weight': 2,
    },

    # --- LATAM ---
    'latam': {
        'category': 'LatAm',
        'patterns': [
            r'(?:brasil|méxico|colombia|perú|argentina|latam|latin\s*america|emergentes)',
        ],
        'weight': 1,
    },
}

# Secciones narrativas a analizar (ignoramos tablas de datos)
NARRATIVE_SECTIONS = [
    'resumen_ejecutivo',
    'economia', 'economía',
    'politica_geopolitica', 'politica_y_geopolitica',
    'política_y_geopolítica', 'política_geopolítica',
    'ia_tecnologia', 'inteligencia_artificial_y_tecnologia',
    'inteligencia_artificial_y_tecnología',
    'chile_latam', 'chile_y_latam',
    'mercados', 'mercados_por_activo',
    'sentimiento', 'sentimiento_y_volatilidad',
    'idea_tactica', 'idea_táctica',
    'agenda', 'agenda_del_día',
]


class DailyIntelligenceDigest:
    """
    Genera un digest de inteligencia a partir de reportes diarios AM/PM.

    Extrae: temas dominantes con contexto, evolución de sentimiento,
    ideas tácticas categorizadas, y narrativas clave por semana.
    """

    def __init__(self, reports_path: Optional[str] = None, business_days: int = 22):
        """
        Args:
            reports_path: Ruta a carpeta con HTMLs. None = default.
            business_days: Días hábiles a cubrir (22 ≈ 1 mes laboral).
        """
        self.parser = DailyReportParser(reports_path) if reports_path else DailyReportParser()
        self.business_days = business_days
        # 22 business days ≈ 30 calendar days + margen para feriados
        self._calendar_days = int(business_days * 1.6)

    def generate(self) -> Dict[str, Any]:
        """
        Genera el digest completo de inteligencia.

        Returns:
            Dict con:
                - metadata: período, conteo de reportes
                - themes: temas dominantes con contexto y evolución
                - sentiment_evolution: sentimiento por semana
                - tactical_ideas: ideas categorizadas por asset class
                - weekly_narratives: resumen narrativo por semana
                - key_events: eventos/datos mencionados en agenda
        """
        # Parsear todos los reportes disponibles en el período
        reports = self._collect_reports()

        if not reports:
            return {
                'metadata': {'reports_count': 0, 'error': 'No se encontraron reportes'},
                'themes': {},
                'sentiment_evolution': [],
                'tactical_ideas': [],
                'weekly_narratives': [],
                'key_events': [],
            }

        # Generar cada componente del digest
        themes = self._analyze_themes(reports)
        sentiment = self._track_sentiment(reports)
        ideas = self._categorize_ideas(reports)
        weekly = self._build_weekly_narratives(reports)
        events = self._extract_events(reports)

        dates = [r['date'] for r in reports]
        return {
            'metadata': {
                'period': f"{min(dates)} a {max(dates)}",
                'reports_count': len(reports),
                'business_days_covered': len(set(dates)),
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
            },
            'themes': themes,
            'sentiment_evolution': sentiment,
            'tactical_ideas': ideas,
            'weekly_narratives': weekly,
            'key_events': events,
        }

    # =====================================================================
    # RECOLECCIÓN
    # =====================================================================

    def _collect_reports(self) -> List[Dict]:
        """Parsea reportes AM+PM no_finanzas de los últimos N días hábiles."""
        paths = self.parser.list_reports(
            report_type='no_finanzas',
            days=self._calendar_days
        )

        reports = []
        for path in paths:
            try:
                parsed = self.parser.parse_report(path)
                # Concatenar todas las secciones narrativas en un solo texto
                narrative_parts = []
                for section_key in NARRATIVE_SECTIONS:
                    text = parsed.get(section_key, '')
                    if not text:
                        text = parsed.get('sections', {}).get(section_key, '')
                    if text:
                        narrative_parts.append(text)

                parsed['full_narrative'] = '\n'.join(narrative_parts)
                reports.append(parsed)
            except Exception:
                continue

        return reports

    # =====================================================================
    # ANÁLISIS DE TEMAS
    # =====================================================================

    def _analyze_themes(self, reports: List[Dict]) -> Dict[str, Dict]:
        """
        Identifica temas dominantes con contexto narrativo.

        Para cada tema detectado, extrae:
        - Frecuencia (en cuántos reportes aparece)
        - Contexto: oraciones relevantes de los reportes más recientes
        - Evolución: presencia por semana (creciente/decreciente/estable)
        - Categoría del tema
        """
        theme_data = {}

        for theme_id, theme_def in THEME_TAXONOMY.items():
            mentions = []  # List of (date, context_sentence)

            for report in reports:
                text = report.get('full_narrative', '')
                if not text:
                    continue

                # Buscar cualquier patrón del tema
                matched = False
                for pattern in theme_def['patterns']:
                    if re.search(pattern, text, re.IGNORECASE):
                        matched = True
                        break

                if matched:
                    # Extraer oraciones relevantes como contexto
                    contexts = self._extract_context_sentences(
                        text, theme_def['patterns'], max_sentences=2
                    )
                    mentions.append({
                        'date': report['date'],
                        'type': report.get('type', ''),
                        'contexts': contexts,
                    })

            if not mentions:
                continue

            # Calcular presencia por semana
            weekly_presence = self._compute_weekly_presence(mentions)

            # Determinar tendencia
            trend = self._compute_trend(weekly_presence)

            # Score = frecuencia × peso
            score = len(mentions) * theme_def['weight']

            # Extraer los contextos más recientes (últimos 3 reportes con mención)
            recent_contexts = []
            for m in mentions[-3:]:
                for ctx in m['contexts']:
                    recent_contexts.append(f"[{m['date']}] {ctx}")

            theme_data[theme_id] = {
                'category': theme_def['category'],
                'mention_count': len(mentions),
                'report_days': len(set(m['date'] for m in mentions)),
                'score': score,
                'trend': trend,
                'weekly_presence': weekly_presence,
                'recent_contexts': recent_contexts[-5:],  # Max 5
            }

        # Ordenar por score descendente
        theme_data = dict(
            sorted(theme_data.items(), key=lambda x: x[1]['score'], reverse=True)
        )

        return theme_data

    def _extract_context_sentences(
        self, text: str, patterns: List[str], max_sentences: int = 2
    ) -> List[str]:
        """Extrae oraciones que contienen los patrones del tema."""
        # Dividir en oraciones (por punto, punto y coma, o salto de línea)
        sentences = re.split(r'(?<=[.!?;])\s+|\n+', text)
        matches = []

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 15:
                continue
            for pattern in patterns:
                if re.search(pattern, sentence, re.IGNORECASE):
                    # Limpiar y truncar
                    clean = sentence[:300]
                    if clean not in matches:
                        matches.append(clean)
                    break

            if len(matches) >= max_sentences:
                break

        return matches

    def _compute_weekly_presence(self, mentions: List[Dict]) -> List[Dict]:
        """Agrupa menciones por semana ISO y cuenta presencia."""
        weeks = defaultdict(int)
        for m in mentions:
            try:
                dt = datetime.strptime(m['date'], '%Y-%m-%d')
                week_key = dt.strftime('%Y-W%W')
                weeks[week_key] += 1
            except ValueError:
                continue

        return [{'week': k, 'mentions': v} for k, v in sorted(weeks.items())]

    def _compute_trend(self, weekly_presence: List[Dict]) -> str:
        """Determina si un tema va en aumento, disminución o estable."""
        if len(weekly_presence) < 2:
            return 'nuevo' if weekly_presence else 'inactivo'

        # Comparar primera mitad vs segunda mitad
        mid = len(weekly_presence) // 2
        first_half = sum(w['mentions'] for w in weekly_presence[:mid])
        second_half = sum(w['mentions'] for w in weekly_presence[mid:])

        if second_half > first_half * 1.3:
            return 'creciente'
        elif second_half < first_half * 0.7:
            return 'decreciente'
        else:
            return 'estable'

    # =====================================================================
    # SENTIMIENTO
    # =====================================================================

    def _track_sentiment(self, reports: List[Dict]) -> List[Dict]:
        """
        Rastrea evolución de sentimiento por semana.

        Analiza la sección de sentimiento + resumen ejecutivo para determinar
        el tono general: risk-on, risk-off, cauteloso, neutral.
        """
        # Palabras asociadas a cada tono
        RISK_ON = [
            'rally', 'sube', 'suben', 'avanza', 'avanzan', 'máximo',
            'optimismo', 'risk.?on', 'bullish', 'recupera', 'impulsa',
            'fortalece', 'positiv', 'verde',
        ]
        RISK_OFF = [
            'cae', 'caen', 'baja', 'bajan', 'desplom', 'pánico',
            'risk.?off', 'bearish', 'sell.?off', 'temor', 'miedo',
            'rojo', 'presión', 'preocupa', 'retrocede', 'debilita',
        ]
        CAUTIOUS = [
            'cautela', 'cauteloso', 'incertidumbre', 'mixto', 'mixta',
            'volátil', 'volatilidad', 'espera', 'prudencia', 'moderado',
        ]

        daily_sentiment = []
        for report in reports:
            text = (
                report.get('resumen_ejecutivo', '') + ' ' +
                report.get('sentimiento', '') + ' ' +
                report.get('sentimiento_y_volatilidad', '') + ' ' +
                report.get('sections', {}).get('sentimiento_y_volatilidad', '')
            ).lower()

            if not text.strip():
                continue

            on_score = sum(1 for w in RISK_ON if re.search(w, text))
            off_score = sum(1 for w in RISK_OFF if re.search(w, text))
            caut_score = sum(1 for w in CAUTIOUS if re.search(w, text))

            total = on_score + off_score + caut_score
            if total == 0:
                tone = 'neutral'
            elif on_score > off_score and on_score > caut_score:
                tone = 'risk-on'
            elif off_score > on_score and off_score > caut_score:
                tone = 'risk-off'
            elif caut_score >= on_score and caut_score >= off_score:
                tone = 'cauteloso'
            else:
                tone = 'neutral'

            daily_sentiment.append({
                'date': report['date'],
                'type': report.get('type', ''),
                'tone': tone,
                'scores': {'risk_on': on_score, 'risk_off': off_score, 'cautious': caut_score},
            })

        # Agregar por semana
        weeks = defaultdict(lambda: {'risk_on': 0, 'risk_off': 0, 'cautious': 0, 'count': 0})
        for s in daily_sentiment:
            try:
                dt = datetime.strptime(s['date'], '%Y-%m-%d')
                week_key = dt.strftime('%Y-W%W')
            except ValueError:
                continue
            weeks[week_key]['risk_on'] += s['scores']['risk_on']
            weeks[week_key]['risk_off'] += s['scores']['risk_off']
            weeks[week_key]['cautious'] += s['scores']['cautious']
            weeks[week_key]['count'] += 1

        weekly_sentiment = []
        for week_key in sorted(weeks):
            w = weeks[week_key]
            n = w['count'] or 1
            dominant = max(
                [('risk-on', w['risk_on']), ('risk-off', w['risk_off']), ('cauteloso', w['cautious'])],
                key=lambda x: x[1]
            )
            weekly_sentiment.append({
                'week': week_key,
                'reports': w['count'],
                'dominant_tone': dominant[0],
                'avg_risk_on': round(w['risk_on'] / n, 1),
                'avg_risk_off': round(w['risk_off'] / n, 1),
                'avg_cautious': round(w['cautious'] / n, 1),
            })

        return weekly_sentiment

    # =====================================================================
    # IDEAS TÁCTICAS
    # =====================================================================

    def _categorize_ideas(self, reports: List[Dict]) -> List[Dict]:
        """
        Extrae y categoriza ideas tácticas por clase de activo.
        """
        CATEGORIES = {
            'Renta Variable': [
                r'(?:accion|bolsa|s&p|nasdaq|ipsa|índice|equity|sobreponderar|subponderar)',
                r'(?:tech|sector|rotación)',
            ],
            'Renta Fija': [
                r'(?:bono|treasury|duration|curva|yield|spread|crédito|renta\s+fija)',
            ],
            'Commodities': [
                r'(?:cobre|oro|petróleo|commodity|metal|energía)',
            ],
            'Divisas': [
                r'(?:dólar|peso|eur|jpy|moneda|divisa|tipo\s+de\s+cambio|fx)',
            ],
            'Cobertura': [
                r'(?:cobertura|hedge|put|opción|vix|protección)',
            ],
        }

        ideas = []
        for report in reports:
            idea_text = report.get('idea_tactica', '')
            if not idea_text:
                sections = report.get('sections', {})
                idea_text = (
                    sections.get('idea_tactica', '') or
                    sections.get('idea_táctica', '') or
                    sections.get('lectura__idea_táctica', '') or
                    sections.get('lectura_idea_táctica', '')
                )
            if not idea_text or len(idea_text) < 20:
                continue

            # Clasificar por categoría
            category = 'General'
            idea_lower = idea_text.lower()
            for cat_name, patterns in CATEGORIES.items():
                for p in patterns:
                    if re.search(p, idea_lower):
                        category = cat_name
                        break
                if category != 'General':
                    break

            ideas.append({
                'date': report['date'],
                'type': report.get('type', ''),
                'category': category,
                'idea': idea_text[:500],
            })

        return ideas

    # =====================================================================
    # NARRATIVAS SEMANALES
    # =====================================================================

    def _build_weekly_narratives(self, reports: List[Dict]) -> List[Dict]:
        """
        Construye un resumen narrativo por semana basado en resúmenes ejecutivos.
        Agrupa los bullets más importantes de cada semana.
        """
        weeks = defaultdict(list)

        for report in reports:
            resumen = report.get('resumen_ejecutivo', '')
            if not resumen:
                continue
            try:
                dt = datetime.strptime(report['date'], '%Y-%m-%d')
                week_key = dt.strftime('%Y-W%W')
            except ValueError:
                continue

            # Extraer bullets (cada línea que empieza con • o -)
            bullets = re.findall(r'[•\-]\s*(.+?)(?=\n|$)', resumen)
            if not bullets:
                # Si no hay bullets, tomar oraciones
                bullets = [s.strip() for s in resumen.split('.') if len(s.strip()) > 20]

            for b in bullets[:3]:  # Max 3 bullets por reporte
                weeks[week_key].append({
                    'date': report['date'],
                    'bullet': b.strip()[:200],
                })

        weekly_narratives = []
        for week_key in sorted(weeks):
            bullets = weeks[week_key]
            # Tomar los bullets más recientes de la semana (últimos 6)
            recent = bullets[-6:]
            weekly_narratives.append({
                'week': week_key,
                'report_days': len(set(b['date'] for b in bullets)),
                'highlights': [b['bullet'] for b in recent],
            })

        return weekly_narratives

    # =====================================================================
    # EVENTOS / AGENDA
    # =====================================================================

    def _extract_events(self, reports: List[Dict]) -> List[Dict]:
        """Extrae eventos de la sección Agenda de los reportes recientes."""
        events = []
        seen = set()

        # Solo últimos 5 reportes para agenda (eventos pasados no sirven)
        for report in reports[-5:]:
            sections = report.get('sections', {})
            agenda = (
                sections.get('agenda', '') or
                sections.get('agenda_del_día', '') or
                sections.get('agenda_del_dia', '')
            )
            if not agenda:
                continue

            # Cada línea o oración es un evento potencial
            for line in re.split(r'\n|(?<=[.])\s+', agenda):
                line = line.strip()
                if len(line) < 15:
                    continue
                # Dedup por similitud simple
                key = line[:50].lower()
                if key not in seen:
                    seen.add(key)
                    events.append({
                        'from_date': report['date'],
                        'event': line[:300],
                    })

        return events[-10:]  # Últimos 10

    # =====================================================================
    # FORMATO PARA EL COUNCIL
    # =====================================================================

    def format_for_council(self, digest: Dict) -> str:
        """
        Formatea el digest como texto estructurado para inyectar en los
        prompts del AI Council.

        Diseñado para ser conciso pero informativo — el council necesita
        entender QUÉ está pasando y CÓMO ha evolucionado.
        """
        meta = digest['metadata']
        lines = []

        lines.append("=" * 60)
        lines.append("DAILY INTELLIGENCE DIGEST")
        lines.append(f"Período: {meta.get('period', 'N/A')}")
        lines.append(f"Reportes analizados: {meta.get('reports_count', 0)} "
                      f"({meta.get('business_days_covered', 0)} días hábiles)")
        lines.append("=" * 60)

        # --- TEMAS DOMINANTES ---
        lines.append("\n## TEMAS DOMINANTES\n")
        themes = digest.get('themes', {})
        top_themes = list(themes.items())[:10]

        for theme_id, t in top_themes:
            trend_icon = {
                'creciente': '[+]',
                'decreciente': '[-]',
                'estable': '[=]',
                'nuevo': '[*]',
            }.get(t['trend'], '[?]')

            lines.append(
                f"### {theme_id.upper()} [{t['category']}] "
                f"— {t['report_days']} días, tendencia {t['trend']} {trend_icon}"
            )

            # Contextos recientes (máx 3)
            for ctx in t['recent_contexts'][:3]:
                lines.append(f"  > {ctx}")
            lines.append("")

        # --- EVOLUCIÓN DE SENTIMIENTO ---
        lines.append("\n## EVOLUCIÓN DE SENTIMIENTO\n")
        for ws in digest.get('sentiment_evolution', []):
            lines.append(
                f"  {ws['week']} ({ws['reports']} reportes): "
                f"{ws['dominant_tone'].upper()} "
                f"(on:{ws['avg_risk_on']} / off:{ws['avg_risk_off']} / cautela:{ws['avg_cautious']})"
            )

        # --- IDEAS TÁCTICAS ---
        lines.append("\n\n## IDEAS TÁCTICAS RECIENTES\n")
        ideas = digest.get('tactical_ideas', [])
        for idea in ideas[-8:]:  # Últimas 8
            lines.append(
                f"  [{idea['date']}] ({idea['category']}) {idea['idea'][:200]}"
            )

        # --- NARRATIVAS SEMANALES ---
        lines.append("\n\n## NARRATIVAS SEMANALES\n")
        for wn in digest.get('weekly_narratives', []):
            lines.append(f"### Semana {wn['week']} ({wn['report_days']} días)")
            for h in wn['highlights'][:4]:
                lines.append(f"  - {h}")
            lines.append("")

        # --- EVENTOS PRÓXIMOS ---
        events = digest.get('key_events', [])
        if events:
            lines.append("\n## EVENTOS / AGENDA\n")
            for ev in events:
                lines.append(f"  [{ev['from_date']}] {ev['event']}")

        return '\n'.join(lines)

    # =====================================================================
    # RESUMEN COMPACTO (para contexto limitado)
    # =====================================================================

    def format_compact(self, digest: Dict, max_chars: int = 4000) -> str:
        """
        Versión compacta del digest para agentes con contexto limitado.
        Prioriza temas top y sentimiento.
        """
        lines = []
        meta = digest['metadata']
        lines.append(
            f"INTELLIGENCE DIGEST: {meta.get('period', 'N/A')} "
            f"({meta.get('reports_count', 0)} reportes)\n"
        )

        # Top 5 temas con contexto mínimo
        lines.append("TEMAS TOP:")
        for theme_id, t in list(digest.get('themes', {}).items())[:5]:
            ctx = t['recent_contexts'][0] if t['recent_contexts'] else 'sin contexto'
            lines.append(f"- {theme_id} ({t['category']}, {t['trend']}): {ctx[:150]}")

        # Sentimiento última semana
        sentiment = digest.get('sentiment_evolution', [])
        if sentiment:
            last = sentiment[-1]
            lines.append(f"\nSENTIMIENTO ACTUAL: {last['dominant_tone'].upper()}")

        # Última idea táctica
        ideas = digest.get('tactical_ideas', [])
        if ideas:
            last_idea = ideas[-1]
            lines.append(f"\nÚLTIMA IDEA: [{last_idea['date']}] {last_idea['idea'][:200]}")

        result = '\n'.join(lines)
        return result[:max_chars]


# =========================================================================
# MAIN
# =========================================================================

def main():
    """Test del Daily Intelligence Digest."""
    print("=" * 60)
    print("DAILY INTELLIGENCE DIGEST - TEST")
    print("=" * 60)

    digest = DailyIntelligenceDigest(business_days=22)
    result = digest.generate()

    meta = result['metadata']
    print(f"\nPeríodo: {meta.get('period', 'N/A')}")
    print(f"Reportes: {meta.get('reports_count', 0)}")
    print(f"Días hábiles: {meta.get('business_days_covered', 0)}")

    # Temas
    print(f"\n--- TEMAS ({len(result['themes'])} detectados) ---")
    for theme_id, t in list(result['themes'].items())[:10]:
        print(f"  {theme_id:25s}  [{t['category']:18s}]  "
              f"días={t['report_days']:2d}  trend={t['trend']:12s}  score={t['score']}")
        for ctx in t['recent_contexts'][:1]:
            print(f"    > {ctx[:120]}...")

    # Sentimiento
    print(f"\n--- SENTIMIENTO ---")
    for ws in result['sentiment_evolution']:
        print(f"  {ws['week']}: {ws['dominant_tone']:12s} "
              f"(on:{ws['avg_risk_on']} off:{ws['avg_risk_off']} caut:{ws['avg_cautious']})")

    # Ideas tácticas
    print(f"\n--- IDEAS TÁCTICAS ({len(result['tactical_ideas'])} total) ---")
    for idea in result['tactical_ideas'][-5:]:
        print(f"  [{idea['date']}] ({idea['category']:15s}) {idea['idea'][:100]}...")

    # Weekly narratives
    print(f"\n--- NARRATIVAS SEMANALES ---")
    for wn in result['weekly_narratives']:
        print(f"  {wn['week']} ({wn['report_days']} días):")
        for h in wn['highlights'][:2]:
            print(f"    - {h[:100]}...")

    # Formato council
    print("\n" + "=" * 60)
    print("FORMATO COUNCIL (primeros 3000 chars):")
    print("=" * 60)
    formatted = digest.format_for_council(result)
    print(formatted[:3000])

    print(f"\n\nTotal chars formato council: {len(formatted)}")
    print(f"Total chars formato compacto: {len(digest.format_compact(result))}")


if __name__ == "__main__":
    main()
