# -*- coding: utf-8 -*-
"""
Greybark Research - Intelligence Briefing Renderer
====================================================

Combina el template HTML con los datos del briefing generado por
IntelligenceBriefingGenerator para producir un informe HTML profesional.

Sigue el mismo patrón que MacroReportRenderer:
  1. Carga template
  2. Genera HTML sections desde briefing_data dict
  3. Reemplaza placeholders
  4. Guarda en output/reports/

Uso:
    renderer = IntelligenceBriefingRenderer(briefing_data)
    path = renderer.render()
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from jinja2 import Environment, FileSystemLoader, Undefined


MESES_ES = {
    1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
    5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
    9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre',
}


class IntelligenceBriefingRenderer:
    """Renderiza el briefing de inteligencia como HTML profesional."""

    def __init__(self, briefing_data: Dict[str, Any], verbose: bool = True, branding: dict = None):
        self.briefing = briefing_data
        self.verbose = verbose
        self.branding = branding or {}
        self.template_path = Path(__file__).parent / "templates" / "intelligence_briefing_professional.html"
        self.template_name = "intelligence_briefing_professional.html"
        self.output_dir = Path(__file__).parent / "output" / "reports"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
            undefined=Undefined,
            autoescape=False,
        )

    def _print(self, msg: str):
        if self.verbose:
            print(f"  {msg}")

    def render(self, output_filename: str = None) -> str:
        """
        Renderiza el briefing como HTML y lo guarda.
        Returns: path al archivo generado.
        """
        self._print("[Renderer] Cargando template...")

        # Load template via Jinja2
        template = self._jinja_env.get_template(self.template_name)

        # Build replacements and convert keys for Jinja2
        replacements = self._build_replacements()
        context = {}
        for key, value in replacements.items():
            clean = key.replace('{{', '').replace('}}', '')
            context[clean] = str(value)

        # Inject branding (templates use |default() for fallback)
        if self.branding:
            context.update(self.branding)

        html = template.render(**context)

        # Output filename
        if not output_filename:
            date_str = datetime.now().strftime('%Y-%m-%d')
            output_filename = f"intelligence_briefing_{date_str}.html"

        output_path = self.output_dir / output_filename
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

        self._print(f"[Renderer] Briefing guardado: {output_path}")
        return str(output_path)

    def _build_replacements(self) -> Dict[str, str]:
        """Genera el dict de placeholders → HTML."""
        replacements = {}
        now = datetime.now()

        # Metadata
        meta = self.briefing.get('metadata', {})
        replacements['{{fecha_reporte}}'] = f"{now.day} {MESES_ES.get(now.month, '')} {now.year}"
        replacements['{{reports_count}}'] = str(meta.get('reports_analyzed', 0))
        replacements['{{period}}'] = meta.get('period', '')
        replacements['{{generated_at}}'] = meta.get('generated_at', now.strftime('%Y-%m-%d %H:%M'))

        # Executive summary
        replacements['{{executive_summary}}'] = self.briefing.get('executive_summary', '')

        # Delta semanal
        delta = self.briefing.get('delta_semanal', {})
        replacements['{{delta_nuevos}}'] = self._render_delta_items(delta.get('nuevos', []), 'NUEVO', 'badge-nuevo')
        replacements['{{delta_acelerando}}'] = self._render_delta_items(delta.get('acelerando', []), 'ACELERANDO', 'badge-acelerando')
        replacements['{{delta_desacelerando}}'] = self._render_delta_items(delta.get('desacelerando', []), 'DESACELERANDO', 'badge-desacelerando')

        # Sentiment trajectory
        traj = self.briefing.get('sentiment_trajectory', {})
        replacements['{{sentiment_trajectory}}'] = traj.get('trajectory_str', 'N/A')
        velocity = traj.get('velocity', '')
        replacements['{{sentiment_velocity}}'] = f"Cambio {velocity}" if velocity else ''
        replacements['{{sentiment_bars_html}}'] = self._render_sentiment_bars(traj.get('trajectory', []))

        # Top themes
        replacements['{{top_themes_html}}'] = self._render_top_themes(self.briefing.get('top_themes', []))

        # Contradictory signals
        replacements['{{contradictorias_html}}'] = self._render_contradictions(self.briefing.get('senales_contradictorias', []))

        # Key questions
        replacements['{{preguntas_html}}'] = self._render_questions(self.briefing.get('preguntas_clave', []))

        # Tactical ideas
        replacements['{{ideas_tacticas_html}}'] = self._render_ideas(self.briefing.get('ideas_tacticas', []))

        return replacements

    # =====================================================================
    # SECTION RENDERERS
    # =====================================================================

    def _render_delta_items(self, items: list, label: str, badge_class: str) -> str:
        if not items:
            return ''
        html_parts = []
        for item in items:
            context = item.get('context', '')
            change = ''
            if 'change_pct' in item:
                sign = '+' if item['change_pct'] > 0 else ''
                change = f" ({sign}{item['change_pct']}%)"
            html_parts.append(
                f'<div class="delta-item">'
                f'<span class="delta-badge {badge_class}">{label}</span>'
                f'<span class="delta-text"><strong>{item["category"]}</strong>{change} &mdash; {context}</span>'
                f'</div>'
            )
        return '\n'.join(html_parts)

    def _render_sentiment_bars(self, trajectory: list) -> str:
        if not trajectory:
            return '<div style="text-align:center; color:#717171; font-size:9pt;">Sin datos de sentimiento</div>'
        html_parts = []
        tone_labels = {
            'risk-on': 'Risk-On',
            'risk-off': 'Risk-Off',
            'cauteloso': 'Cauteloso',
            'neutral': 'Neutral',
        }
        for week in trajectory:
            week_label = week.get('week', '')[-3:]  # e.g., "W07"
            risk_on = week.get('risk_on', 0)
            cautious = week.get('cautious', 0)
            risk_off = week.get('risk_off', 0)
            total = risk_on + cautious + risk_off
            if total == 0:
                total = 1
            pct_on = (risk_on / total) * 100
            pct_cau = (cautious / total) * 100
            pct_off = (risk_off / total) * 100
            tone = tone_labels.get(week.get('tone', 'neutral'), 'Neutral')
            html_parts.append(
                f'<div class="sentiment-week">'
                f'<span class="sentiment-week-label">{week_label}</span>'
                f'<div class="sentiment-bar">'
                f'<div class="bar-risk-on" style="width:{pct_on:.0f}%"></div>'
                f'<div class="bar-cautious" style="width:{pct_cau:.0f}%"></div>'
                f'<div class="bar-risk-off" style="width:{pct_off:.0f}%"></div>'
                f'</div>'
                f'<span class="sentiment-tone-label">{tone}</span>'
                f'</div>'
            )
        return '\n'.join(html_parts)

    def _render_top_themes(self, themes: list) -> str:
        if not themes:
            return '<div style="color:#717171; font-size:9pt;">Sin temas detectados</div>'
        max_score = max(t.get('score', 1) for t in themes) or 1
        html_parts = []
        trend_classes = {
            'creciente': ('trend-up', 'Creciente'),
            'decreciente': ('trend-down', 'Decreciente'),
            'estable': ('trend-neutral', 'Estable'),
            'nuevo': ('trend-new', 'Nuevo'),
        }
        for i, t in enumerate(themes, 1):
            bar_pct = (t.get('score', 0) / max_score) * 100
            trend = t.get('trend', 'estable')
            trend_class, trend_label = trend_classes.get(trend, ('trend-neutral', 'Estable'))
            context = t.get('context', '')
            html_parts.append(
                f'<div class="theme-item">'
                f'<div class="theme-rank">{i}</div>'
                f'<div class="theme-info">'
                f'<div class="theme-name">{t["category"]}</div>'
                f'<div class="theme-context">{context}</div>'
                f'</div>'
                f'<div class="theme-bar-container">'
                f'<div class="theme-bar"><div class="theme-bar-fill" style="width:{bar_pct:.0f}%"></div></div>'
                f'<div class="theme-trend {trend_class}">{trend_label}</div>'
                f'</div>'
                f'</div>'
            )
        return '\n'.join(html_parts)

    def _render_contradictions(self, signals: list) -> str:
        if not signals:
            return '<div style="color:#717171; font-size:9pt;">No se detectaron se&ntilde;ales contradictorias.</div>'
        html_parts = []
        for s in signals:
            html_parts.append(
                f'<div class="signal-card">'
                f'<div class="signal-vs">'
                f'<span class="signal-a">{s["signal_a"]}</span>'
                f'<span class="signal-vs-label">vs</span>'
                f'<span class="signal-b">{s["signal_b"]}</span>'
                f'</div>'
                f'<div class="signal-implication">{s["implication"]}</div>'
                f'</div>'
            )
        return '\n'.join(html_parts)

    def _render_questions(self, questions: list) -> str:
        if not questions:
            return '<div style="color:#717171; font-size:9pt;">Sin preguntas generadas.</div>'
        html_parts = []
        for i, q in enumerate(questions, 1):
            html_parts.append(
                f'<div class="question-item">'
                f'<div class="question-number">{i}</div>'
                f'<div class="question-text">{q}</div>'
                f'</div>'
            )
        return '\n'.join(html_parts)

    def _render_ideas(self, ideas: list) -> str:
        if not ideas:
            return '<div style="color:#717171; font-size:9pt;">Sin ideas t&aacute;cticas vigentes.</div>'
        rows = []
        for idea in ideas:
            stale = '<span class="stale-tag">STALE</span>' if idea.get('stale') else ''
            rows.append(
                f'<tr>'
                f'<td>{idea["date"]}</td>'
                f'<td><span class="category-tag">{idea["category"]}</span></td>'
                f'<td>{idea["idea"]}{stale}</td>'
                f'</tr>'
            )
        return (
            '<table class="ideas-table">'
            '<thead><tr><th>Fecha</th><th>Categor&iacute;a</th><th>Idea</th></tr></thead>'
            '<tbody>' + '\n'.join(rows) + '</tbody>'
            '</table>'
        )


# =========================================================================
# STANDALONE TEST
# =========================================================================

if __name__ == '__main__':
    import json

    print("=" * 60)
    print("Intelligence Briefing Renderer — Test")
    print("=" * 60)
    print("\nEste test usa datos REALES del intelligence digest.")
    print("Generando desde daily_intelligence_digest...\n")

    try:
        from intelligence_briefing_generator import IntelligenceBriefingGenerator
        from daily_intelligence_digest import DailyIntelligenceDigest

        digest = DailyIntelligenceDigest()
        intelligence = digest.generate()
        daily_context = digest.format_for_council(intelligence)

        n_themes = len(intelligence.get('themes', {}))
        n_ideas = len(intelligence.get('tactical_ideas', []))
        print(f"  Intelligence: {n_themes} temas, {n_ideas} ideas")

        if intelligence.get('metadata', {}).get('reports_count', 0) == 0:
            print("\n  [SKIP] No hay reportes disponibles para generar briefing.")
            print("  Asegurate de tener reportes AM/PM en html_out/")
        else:
            gen = IntelligenceBriefingGenerator(intelligence, daily_context)
            briefing = gen.generate_briefing()

            renderer = IntelligenceBriefingRenderer(briefing)
            path = renderer.render()
            print(f"\nGenerated: {path}")
            print("Open in browser to verify layout.")

    except Exception as e:
        print(f"\n  [ERROR] {e}")
        import traceback
        traceback.print_exc()
