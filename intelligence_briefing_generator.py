# -*- coding: utf-8 -*-
"""
Greybark Research - Intelligence Briefing Generator
=====================================================

Genera un briefing ejecutivo pre-comité a partir del intelligence digest.
Análisis 100% programático (sin LLM call): delta semanal, señales
contradictorias, temas top, trayectoria de sentimiento, preguntas clave,
e ideas tácticas vigentes.

El briefing resultante (~2K chars formateado) reemplaza el daily_context
truncado (~10K) en los prompts de los agentes del AI Council.

Uso:
    gen = IntelligenceBriefingGenerator(intelligence, daily_context, directives)
    briefing = gen.generate_briefing()
    council_text = gen.format_for_council()
"""

from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple


# =========================================================================
# PARES CONTRADICTORIOS
# =========================================================================
# Taxonomía de señales que, al coexistir, indican tensión en el mercado.
# Cada par: (tema_a, tema_b, implicación si ambos presentes)

CONTRADICTORY_PAIRS = [
    {
        'theme_a': ['risk_on', 'equity_bullish'],
        'theme_b': ['vix_elevado', 'volatilidad', 'credit_stress'],
        'label_a': 'Sentimiento risk-on',
        'label_b': 'VIX elevado / stress crediticio',
        'implication': 'Divergencia entre posicionamiento y protección — posible complacencia',
    },
    {
        'theme_a': ['fed_dovish', 'fed_política'],
        'theme_b': ['inflacion_persistente', 'breakevens_subiendo'],
        'label_a': 'Fed dovish / recortes esperados',
        'label_b': 'Inflación persistente / breakevens subiendo',
        'implication': 'Mercado descuenta recortes que la inflación podría impedir',
    },
    {
        'theme_a': ['earnings_positivos', 'equity_bullish'],
        'theme_b': ['forward_guidance_negativo', 'earnings_negativos'],
        'label_a': 'Earnings positivos / equity bullish',
        'label_b': 'Forward guidance negativo',
        'implication': 'Resultados backward-looking buenos vs perspectivas deteriorándose',
    },
    {
        'theme_a': ['china_estimulo', 'em_positivo'],
        'theme_b': ['dolar_fuerte', 'trade_war'],
        'label_a': 'China estímulo / EM positivo',
        'label_b': 'Dólar fuerte / tensión comercial',
        'implication': 'Impulso chino choca con condiciones financieras restrictivas globales',
    },
    {
        'theme_a': ['commodities_alza', 'petroleo_alza'],
        'theme_b': ['recesion_riesgo', 'demanda_debil'],
        'label_a': 'Commodities al alza',
        'label_b': 'Riesgo recesivo / demanda débil',
        'implication': 'Alza de commodities por oferta, no por demanda — posible estanflación',
    },
    {
        'theme_a': ['credit_tight', 'credit_stress'],
        'theme_b': ['equity_bullish', 'risk_on'],
        'label_a': 'Spreads crediticios ensanchando',
        'label_b': 'Equity en alza / risk-on',
        'implication': 'Crédito advierte riesgo que equity ignora — históricamente crédito lidera',
    },
]

# Mapping: theme keywords to theme_ids from THEME_TAXONOMY
# This maps conceptual labels to actual theme_ids used in the intelligence dict
THEME_KEYWORD_MAP = {
    'risk_on': ['risk_on', 'rally', 'optimismo'],
    'equity_bullish': ['equity_rally', 'sp500', 'nasdaq', 'acciones_alza'],
    'vix_elevado': ['vix', 'volatilidad'],
    'volatilidad': ['volatilidad', 'vix'],
    'credit_stress': ['credit_spreads', 'high_yield', 'spreads'],
    'fed_dovish': ['fed_política', 'fed_dovish', 'recorte_tasas'],
    'fed_política': ['fed_política'],
    'inflacion_persistente': ['inflacion', 'cpi', 'pce'],
    'breakevens_subiendo': ['breakeven', 'inflacion_esperada'],
    'earnings_positivos': ['earnings', 'resultados_corporativos'],
    'equity_bullish': ['equity_rally', 'bull'],
    'forward_guidance_negativo': ['guidance_negativo', 'outlook_negativo'],
    'earnings_negativos': ['earnings_miss', 'resultados_negativos'],
    'china_estimulo': ['china', 'pboc', 'estimulo_china'],
    'em_positivo': ['emergentes', 'em_positivo'],
    'dolar_fuerte': ['dolar', 'dxy', 'usd_fuerte'],
    'trade_war': ['aranceles', 'trade_war', 'guerra_comercial'],
    'commodities_alza': ['commodities', 'materias_primas'],
    'petroleo_alza': ['petroleo', 'oil', 'brent', 'wti'],
    'recesion_riesgo': ['recesion', 'desaceleracion', 'contraccion'],
    'demanda_debil': ['demanda_debil', 'consumo_debil'],
    'credit_tight': ['credit_spreads', 'high_yield', 'spreads'],
}


class IntelligenceBriefingGenerator:
    """
    Genera un briefing ejecutivo pre-comité a partir del intelligence digest.
    Análisis 100% programático — no requiere llamadas a LLM.
    """

    def __init__(self, intelligence: Dict, daily_context: str,
                 user_directives: str = '', verbose: bool = True):
        self.intelligence = intelligence
        self.daily_context = daily_context
        self.user_directives = user_directives
        self.verbose = verbose
        self._briefing = None

    def _print(self, msg: str):
        if self.verbose:
            try:
                print(f"  {msg}")
            except UnicodeEncodeError:
                print(f"  {msg.encode('ascii', 'replace').decode()}")

    # =====================================================================
    # GENERATE BRIEFING
    # =====================================================================

    def generate_briefing(self) -> Dict[str, Any]:
        """
        Genera el briefing ejecutivo completo.
        Puro análisis programático del intelligence dict.
        """
        self._print("[Briefing] Generando briefing ejecutivo...")

        metadata = self.intelligence.get('metadata', {})
        themes = self.intelligence.get('themes', {})
        sentiment = self.intelligence.get('sentiment_evolution', [])
        ideas = self.intelligence.get('tactical_ideas', [])

        # A) Delta semanal
        delta = self._compute_delta_semanal(themes)
        self._print(f"  Delta: {len(delta.get('nuevos', []))} nuevos, "
                     f"{len(delta.get('acelerando', []))} acelerando, "
                     f"{len(delta.get('desacelerando', []))} desacelerando")

        # B) Señales contradictorias
        contradictorias = self._detect_contradictory_signals(themes)
        self._print(f"  Señales contradictorias: {len(contradictorias)}")

        # C) Top 5 temas
        top_themes = self._rank_top_themes(themes)
        self._print(f"  Top temas: {len(top_themes)}")

        # D) Trayectoria de sentimiento
        trajectory = self._compute_sentiment_trajectory(sentiment)
        self._print(f"  Sentimiento: {trajectory.get('trajectory_str', 'N/A')}")

        # E) Preguntas clave
        preguntas = self._generate_key_questions(
            delta, contradictorias, trajectory, top_themes
        )
        self._print(f"  Preguntas clave: {len(preguntas)}")

        # F) Ideas tácticas vigentes
        ideas_vigentes = self._filter_active_ideas(ideas)
        self._print(f"  Ideas vigentes: {len(ideas_vigentes)}")

        # G) Executive summary
        executive_summary = self._build_executive_summary(
            metadata, delta, contradictorias, trajectory, top_themes
        )

        self._briefing = {
            'metadata': {
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'reports_analyzed': metadata.get('reports_count', 0),
                'period': metadata.get('period', ''),
            },
            'delta_semanal': delta,
            'senales_contradictorias': contradictorias,
            'top_themes': top_themes,
            'sentiment_trajectory': trajectory,
            'preguntas_clave': preguntas,
            'ideas_tacticas': ideas_vigentes,
            'executive_summary': executive_summary,
        }

        self._print("[Briefing] Briefing generado OK")
        return self._briefing

    # =====================================================================
    # A) DELTA SEMANAL
    # =====================================================================

    def _compute_delta_semanal(self, themes: Dict) -> Dict[str, List]:
        """
        Compara temas de últimos 5 días vs días 6-15.
        Identifica: NUEVOS, ACELERANDO (>50%), DESACELERANDO, ESTABLES.
        """
        nuevos = []
        acelerando = []
        desacelerando = []
        estables = []

        for theme_id, theme_data in themes.items():
            weekly = theme_data.get('weekly_presence', [])
            trend = theme_data.get('trend', 'estable')
            category = theme_data.get('category', '')
            mention_count = theme_data.get('mention_count', 0)

            if not weekly:
                continue

            # Split into recent (last 1-2 weeks) vs earlier
            recent_weeks = weekly[-2:] if len(weekly) >= 2 else weekly
            earlier_weeks = weekly[:-2] if len(weekly) > 2 else []

            recent_mentions = sum(w.get('mentions', 0) for w in recent_weeks)
            earlier_mentions = sum(w.get('mentions', 0) for w in earlier_weeks)

            contexts = theme_data.get('recent_contexts', [])
            context_str = contexts[0][:250] if contexts else ''

            entry = {
                'theme_id': theme_id,
                'category': category,
                'context': context_str,
                'recent_mentions': recent_mentions,
                'earlier_mentions': earlier_mentions,
                'total_mentions': mention_count,
            }

            if trend == 'nuevo' or (earlier_mentions == 0 and recent_mentions > 0):
                nuevos.append(entry)
            elif earlier_mentions > 0:
                change_pct = ((recent_mentions - earlier_mentions) / earlier_mentions) * 100
                entry['change_pct'] = round(change_pct)
                if change_pct > 50:
                    acelerando.append(entry)
                elif change_pct < -30:
                    desacelerando.append(entry)
                else:
                    estables.append(entry)
            else:
                estables.append(entry)

        # Sort by mentions
        nuevos.sort(key=lambda x: x['recent_mentions'], reverse=True)
        acelerando.sort(key=lambda x: x.get('change_pct', 0), reverse=True)
        desacelerando.sort(key=lambda x: x.get('change_pct', 0))

        return {
            'nuevos': nuevos[:5],
            'acelerando': acelerando[:5],
            'desacelerando': desacelerando[:5],
            'estables': estables[:5],
        }

    # =====================================================================
    # B) SEÑALES CONTRADICTORIAS
    # =====================================================================

    def _detect_contradictory_signals(self, themes: Dict) -> List[Dict]:
        """
        Busca pares de señales que se contradicen en los temas activos.
        """
        active_theme_ids = set(themes.keys())
        # Also check via keyword content in recent_contexts
        active_keywords = set()
        for theme_id, theme_data in themes.items():
            active_keywords.add(theme_id)
            # Add category-derived keywords
            cat = theme_data.get('category', '').lower()
            for word in cat.split():
                active_keywords.add(word)
            # Check recent contexts for sentiment keywords
            for ctx in theme_data.get('recent_contexts', []):
                ctx_lower = ctx.lower()
                if any(w in ctx_lower for w in ['risk-on', 'rally', 'bull', 'optimis']):
                    active_keywords.add('risk_on')
                if any(w in ctx_lower for w in ['risk-off', 'sell', 'bear', 'pesimis']):
                    active_keywords.add('risk_off')
                if any(w in ctx_lower for w in ['vix', 'volatil']):
                    active_keywords.add('vix_elevado')
                if any(w in ctx_lower for w in ['spread', 'credit', 'high yield']):
                    active_keywords.add('credit_stress')
                if any(w in ctx_lower for w in ['inflaci', 'cpi', 'pce']):
                    active_keywords.add('inflacion_persistente')
                if any(w in ctx_lower for w in ['recorte', 'dovish', 'baja de tasa']):
                    active_keywords.add('fed_dovish')
                if any(w in ctx_lower for w in ['earning', 'resultado']):
                    active_keywords.add('earnings_positivos')
                if any(w in ctx_lower for w in ['guidance', 'outlook negativ']):
                    active_keywords.add('forward_guidance_negativo')
                if any(w in ctx_lower for w in ['china', 'pboc', 'estímulo']):
                    active_keywords.add('china_estimulo')
                if any(w in ctx_lower for w in ['dólar', 'dxy', 'usd']):
                    active_keywords.add('dolar_fuerte')
                if any(w in ctx_lower for w in ['arancel', 'trade war', 'guerra comercial']):
                    active_keywords.add('trade_war')
                if any(w in ctx_lower for w in ['commodity', 'petróleo', 'oil', 'brent']):
                    active_keywords.add('commodities_alza')
                if any(w in ctx_lower for w in ['recesi', 'desaceler', 'contracci']):
                    active_keywords.add('recesion_riesgo')

        detected = []
        for pair in CONTRADICTORY_PAIRS:
            # Check if any theme_a keyword is active
            a_active = any(
                kw in active_theme_ids or kw in active_keywords
                for kw in pair['theme_a']
            )
            b_active = any(
                kw in active_theme_ids or kw in active_keywords
                for kw in pair['theme_b']
            )

            if a_active and b_active:
                detected.append({
                    'signal_a': pair['label_a'],
                    'signal_b': pair['label_b'],
                    'implication': pair['implication'],
                })

        return detected

    # =====================================================================
    # C) TOP 5 THEMES
    # =====================================================================

    def _rank_top_themes(self, themes: Dict, top_n: int = 10) -> List[Dict]:
        """
        Rankea temas por: score (frecuencia × weight) con bonus de recencia.
        """
        ranked = []

        for theme_id, theme_data in themes.items():
            score = theme_data.get('score', 0)
            trend = theme_data.get('trend', 'estable')
            category = theme_data.get('category', '')
            mention_count = theme_data.get('mention_count', 0)

            # Recency bonus: temas con trend 'nuevo' o 'creciente' get boost
            trend_weight = 1.0
            if trend == 'nuevo':
                trend_weight = 1.5
            elif trend == 'creciente':
                trend_weight = 1.3
            elif trend == 'decreciente':
                trend_weight = 0.7

            final_score = score * trend_weight

            contexts = theme_data.get('recent_contexts', [])
            context_str = contexts[0][:400] if contexts else ''

            ranked.append({
                'theme_id': theme_id,
                'category': category,
                'context': context_str,
                'trend': trend,
                'mention_count': mention_count,
                'score': round(final_score, 1),
            })

        ranked.sort(key=lambda x: x['score'], reverse=True)
        return ranked[:top_n]

    # =====================================================================
    # D) SENTIMIENTO TRAJECTORY
    # =====================================================================

    def _compute_sentiment_trajectory(self, sentiment: List[Dict]) -> Dict:
        """
        Computa la trayectoria de sentimiento de las últimas semanas.
        """
        if not sentiment:
            return {
                'trajectory': [],
                'trajectory_str': 'N/A',
                'velocity': 'sin datos',
                'current': 'neutral',
            }

        # Last 3-4 weeks
        recent = sentiment[-4:] if len(sentiment) >= 4 else sentiment

        trajectory = []
        for week_data in recent:
            tone = week_data.get('dominant_tone', 'neutral')
            trajectory.append({
                'week': week_data.get('week', ''),
                'tone': tone,
                'risk_on': week_data.get('avg_risk_on', 0),
                'risk_off': week_data.get('avg_risk_off', 0),
                'cautious': week_data.get('avg_cautious', 0),
            })

        # Build trajectory string with arrows
        tone_labels = {
            'risk-on': 'RISK-ON',
            'risk-off': 'RISK-OFF',
            'cauteloso': 'CAUTELOSO',
            'neutral': 'NEUTRAL',
        }
        tones = [tone_labels.get(t['tone'], t['tone'].upper()) for t in trajectory]
        trajectory_str = ' → '.join(tones)

        # Velocity: check if last 2 tones are different
        current = tones[-1] if tones else 'NEUTRAL'
        if len(tones) >= 2 and tones[-1] != tones[-2]:
            velocity = 'abrupto'
        elif len(tones) >= 3 and len(set(tones[-3:])) > 2:
            velocity = 'volátil'
        else:
            velocity = 'gradual'

        return {
            'trajectory': trajectory,
            'trajectory_str': trajectory_str,
            'velocity': velocity,
            'current': current,
        }

    # =====================================================================
    # E) PREGUNTAS CLAVE
    # =====================================================================

    def _generate_key_questions(
        self,
        delta: Dict,
        contradictorias: List[Dict],
        trajectory: Dict,
        top_themes: List[Dict],
    ) -> List[str]:
        """
        Genera 2-3 preguntas que el comité debería resolver.
        """
        questions = []

        # From contradictory signals
        for signal in contradictorias[:1]:
            questions.append(
                f"¿Qué pesa más: {signal['signal_a']} o {signal['signal_b']}? "
                f"({signal['implication']})"
            )

        # From new accelerating themes
        for tema in delta.get('acelerando', [])[:1]:
            questions.append(
                f"¿Es sostenible la aceleración en {tema['category']}? "
                f"(+{tema.get('change_pct', '?')}% en menciones recientes)"
            )

        for tema in delta.get('nuevos', [])[:1]:
            if not questions or len(questions) < 2:
                questions.append(
                    f"Tema nuevo: {tema['category']} — "
                    f"¿señal temprana o ruido transitorio?"
                )

        # From sentiment velocity
        if trajectory.get('velocity') == 'abrupto' and len(questions) < 3:
            questions.append(
                f"Sentimiento cambió abruptamente a {trajectory.get('current', '?')} "
                f"— ¿corrección técnica o cambio fundamental?"
            )

        # From dominant themes if we have fewer than 2 questions
        if len(questions) < 2 and top_themes:
            top = top_themes[0]
            questions.append(
                f"Tema dominante: {top['category']} (score {top['score']}) "
                f"— ¿cómo posicionarse?"
            )

        return questions[:3]

    # =====================================================================
    # F) IDEAS TÁCTICAS VIGENTES
    # =====================================================================

    def _filter_active_ideas(self, ideas: List[Dict], max_age_days: int = 14) -> List[Dict]:
        """
        Filtra las últimas ideas tácticas y marca las stale (>5 días).
        """
        today = datetime.now().date()
        active = []

        for idea in ideas:
            idea_date_str = idea.get('date', '')
            try:
                idea_date = datetime.strptime(idea_date_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                continue

            age_days = (today - idea_date).days
            if age_days <= max_age_days:
                active.append({
                    'date': idea_date_str,
                    'category': idea.get('category', 'General'),
                    'idea': idea.get('idea', ''),
                    'stale': age_days > 5,
                    'age_days': age_days,
                })

        # Sort by date descending, take last 15
        active.sort(key=lambda x: x['date'], reverse=True)
        return active[:15]

    # =====================================================================
    # EXECUTIVE SUMMARY
    # =====================================================================

    def _build_executive_summary(
        self,
        metadata: Dict,
        delta: Dict,
        contradictorias: List[Dict],
        trajectory: Dict,
        top_themes: List[Dict],
    ) -> str:
        """
        Genera un párrafo resumen (~200 palabras) de todo lo anterior.
        """
        parts = []

        n_reports = metadata.get('reports_count', 0)
        period = metadata.get('period', '')
        parts.append(f"Análisis de {n_reports} reportes ({period}).")

        # Sentiment
        current = trajectory.get('current', 'NEUTRAL')
        velocity = trajectory.get('velocity', '')
        traj_str = trajectory.get('trajectory_str', '')
        if traj_str:
            parts.append(f"Sentimiento: {traj_str} (cambio {velocity}).")

        # Top themes
        if top_themes:
            top_names = [t['category'] for t in top_themes[:3]]
            parts.append(f"Temas dominantes: {', '.join(top_names)}.")

        # Delta
        n_new = len(delta.get('nuevos', []))
        n_acc = len(delta.get('acelerando', []))
        if n_new > 0 or n_acc > 0:
            delta_parts = []
            if n_new:
                new_names = [t['category'] for t in delta['nuevos'][:2]]
                delta_parts.append(f"{n_new} temas nuevos ({', '.join(new_names)})")
            if n_acc:
                acc_names = [t['category'] for t in delta['acelerando'][:2]]
                delta_parts.append(f"{n_acc} acelerando ({', '.join(acc_names)})")
            parts.append(f"Delta semanal: {'; '.join(delta_parts)}.")

        # Contradictions
        if contradictorias:
            parts.append(
                f"Atención: {len(contradictorias)} señal(es) contradictoria(s) detectada(s) "
                f"— {contradictorias[0]['implication']}."
            )

        return ' '.join(parts)

    # =====================================================================
    # FORMAT FOR COUNCIL
    # =====================================================================

    def format_for_council(self) -> str:
        """
        Formatea el briefing como texto compacto (~2K chars) para inyectar en prompts.
        Reemplaza el daily_context truncado.
        """
        if not self._briefing:
            return ''

        b = self._briefing
        now = datetime.now()
        lines = []

        # Header
        n_reports = b['metadata'].get('reports_analyzed', 0)
        period = b['metadata'].get('period', '')
        lines.append(f"INTELLIGENCE BRIEFING — {now.strftime('%d %b %Y')}")
        lines.append(f"{n_reports} reportes analizados | Período: {period}")
        lines.append('')

        # Delta semanal
        delta = b.get('delta_semanal', {})
        has_delta = any(delta.get(k) for k in ('nuevos', 'acelerando', 'desacelerando'))
        if has_delta:
            lines.append('DELTA SEMANAL:')
            for tema in delta.get('nuevos', [])[:3]:
                lines.append(f"  NUEVO: {tema['category']} — {tema['context'][:80]}")
            for tema in delta.get('acelerando', [])[:3]:
                lines.append(
                    f"  ACELERANDO: {tema['category']} — "
                    f"+{tema.get('change_pct', '?')}% menciones esta semana"
                )
            for tema in delta.get('desacelerando', [])[:2]:
                lines.append(f"  DESACELERANDO: {tema['category']}")
            lines.append('')

        # Sentiment
        traj = b.get('sentiment_trajectory', {})
        if traj.get('trajectory_str'):
            lines.append(
                f"SENTIMIENTO: {traj['trajectory_str']} "
                f"(cambio {traj.get('velocity', 'N/A')})"
            )
            lines.append('')

        # Top themes
        top = b.get('top_themes', [])
        if top:
            lines.append('TOP TEMAS:')
            for i, t in enumerate(top[:5], 1):
                trend_arrow = {'creciente': '↑', 'decreciente': '↓',
                               'estable': '→', 'nuevo': '★'}.get(t['trend'], '→')
                lines.append(
                    f"  {i}. {t['category']} — {t['context'][:200]} — "
                    f"tendencia {t['trend']} {trend_arrow}"
                )
            lines.append('')

        # Contradictory signals
        contras = b.get('senales_contradictorias', [])
        if contras:
            lines.append('SEÑALES CONTRADICTORIAS:')
            for s in contras[:3]:
                lines.append(f"  - {s['signal_a']} vs {s['signal_b']} → {s['implication']}")
            lines.append('')

        # Key questions
        preguntas = b.get('preguntas_clave', [])
        if preguntas:
            lines.append('PREGUNTAS PARA EL COMITÉ:')
            for i, q in enumerate(preguntas, 1):
                lines.append(f"  {i}. {q}")
            lines.append('')

        # Active tactical ideas
        ideas = b.get('ideas_tacticas', [])
        if ideas:
            lines.append('IDEAS TÁCTICAS VIGENTES:')
            for idea in ideas[:5]:
                stale_flag = ' [STALE >5d]' if idea.get('stale') else ''
                lines.append(
                    f"  - [{idea['date']}] {idea['category']}: "
                    f"{idea['idea'][:200]}{stale_flag}"
                )
            lines.append('')

        return '\n'.join(lines)


# =========================================================================
# STANDALONE TEST
# =========================================================================

if __name__ == '__main__':
    import json
    from pathlib import Path

    print("=" * 60)
    print("Intelligence Briefing Generator — Test")
    print("=" * 60)

    # Try to load a saved intelligence JSON
    base = Path(__file__).parent / "output"
    intel_files = sorted(base.glob("**/intelligence*.json"), reverse=True)

    if not intel_files:
        # Generate fresh
        print("\nNo cached intelligence found. Generating fresh...")
        from daily_intelligence_digest import DailyIntelligenceDigest
        digest = DailyIntelligenceDigest()
        intelligence = digest.generate()
        daily_context = digest.format_for_council(intelligence)
    else:
        print(f"\nUsing cached: {intel_files[0]}")
        with open(intel_files[0], 'r', encoding='utf-8') as f:
            intelligence = json.load(f)
        daily_context = ''

    print(f"\nThemes: {len(intelligence.get('themes', {}))}")
    print(f"Sentiment weeks: {len(intelligence.get('sentiment_evolution', []))}")
    print(f"Ideas: {len(intelligence.get('tactical_ideas', []))}")

    # Generate briefing
    gen = IntelligenceBriefingGenerator(intelligence, daily_context)
    briefing = gen.generate_briefing()

    def safe_print(text):
        try:
            print(text)
        except UnicodeEncodeError:
            print(text.encode('ascii', 'replace').decode())

    safe_print(f"\n{'=' * 60}")
    safe_print("BRIEFING RESULT:")
    safe_print(f"{'=' * 60}")
    safe_print(json.dumps(briefing, indent=2, ensure_ascii=False, default=str)[:3000])

    safe_print(f"\n{'=' * 60}")
    safe_print("FORMAT FOR COUNCIL:")
    safe_print(f"{'=' * 60}")
    council_text = gen.format_for_council()
    safe_print(council_text)
    safe_print(f"\n[Length: {len(council_text)} chars]")
