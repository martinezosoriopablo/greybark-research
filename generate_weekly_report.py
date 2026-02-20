# -*- coding: utf-8 -*-
"""
GREY BARK ADVISORS - GENERADOR DE REPORTE SEMANAL
Recopila snapshots diarios y genera informe semanal con tendencias e ideas tácticas
"""

import sys
import io
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import json
import os
import glob
from datetime import date, timedelta, datetime
from typing import Dict, List, Any, Optional
from collections import Counter, defaultdict
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

HISTORY_DIR = "history"
WEEKLY_PROMPT_FILE = "weekly_report_prompt.txt"

# Mapeo de días en español
DIAS_SEMANA = {
    0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
    4: "Viernes", 5: "Sábado", 6: "Domingo"
}

MESES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
}

# ============================================================================
# FUNCIONES DE FECHA
# ============================================================================

def get_week_dates(reference_date: date = None) -> tuple:
    """
    Obtiene las fechas de inicio y fin de la semana.
    Por defecto usa la semana pasada (Lunes a Viernes).
    """
    if reference_date is None:
        reference_date = date.today()

    # Retroceder al lunes de esta semana
    days_since_monday = reference_date.weekday()
    this_monday = reference_date - timedelta(days=days_since_monday)

    # Si estamos en fin de semana o lunes, usar semana pasada
    if reference_date.weekday() <= 0:  # Lunes
        start_date = this_monday - timedelta(days=7)
    else:
        start_date = this_monday

    end_date = start_date + timedelta(days=4)  # Viernes

    return start_date, end_date


def get_week_number(d: date) -> int:
    """Retorna el número de semana del año"""
    return d.isocalendar()[1]


def format_date_spanish(d: date) -> str:
    """Formatea fecha en español: 'Lunes 13 de enero de 2026'"""
    dia_semana = DIAS_SEMANA[d.weekday()]
    mes = MESES[d.month]
    return f"{dia_semana} {d.day} de {mes} de {d.year}"


# ============================================================================
# CARGA DE DATOS
# ============================================================================

def load_weekly_snapshots(start_date: date, end_date: date) -> List[Dict[str, Any]]:
    """
    Carga todos los snapshots diarios de la semana.
    Busca en la carpeta history/ archivos daily_market_snapshot_YYYY-MM-DD_*.json
    """
    snapshots = []
    current_date = start_date

    print(f"\n[INFO] Buscando snapshots del {start_date} al {end_date}...")

    while current_date <= end_date:
        date_str = current_date.isoformat()

        # Buscar AM y PM
        for mode in ["AM", "PM"]:
            pattern = os.path.join(HISTORY_DIR, f"daily_market_snapshot_{date_str}_{mode}.json")
            files = glob.glob(pattern)

            for file_path in files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        data['_file'] = os.path.basename(file_path)
                        data['_mode'] = mode
                        data['_date'] = date_str
                        snapshots.append(data)
                        print(f"  [OK] Cargado: {os.path.basename(file_path)}")
                except Exception as e:
                    print(f"  [ERROR] Error cargando {file_path}: {e}")

        current_date += timedelta(days=1)

    print(f"\n[INFO] Total snapshots cargados: {len(snapshots)}")
    return snapshots


# ============================================================================
# ANÁLISIS DE TENDENCIAS
# ============================================================================

def extract_hot_topics(snapshots: List[Dict]) -> Dict[str, int]:
    """Extrae los temas más mencionados durante la semana"""
    all_topics = Counter()

    for snapshot in snapshots:
        # Hot topics de news_curated
        news_curated = snapshot.get("news_curated", {})
        hot_topics = news_curated.get("cross_newsletter_insights", {}).get("hot_topics", {})

        for topic, count in hot_topics.items():
            all_topics[topic] += count

    return dict(all_topics.most_common(20))


def extract_sentiment_trend(snapshots: List[Dict]) -> List[Dict]:
    """Extrae la evolución del sentimiento durante la semana"""
    trend = []

    for snapshot in snapshots:
        sentiment = snapshot.get("sentiment", {})
        if sentiment:
            trend.append({
                "date": snapshot.get("_date"),
                "mode": snapshot.get("_mode"),
                "sentiment": sentiment.get("sentiment"),
                "score": sentiment.get("score"),
                "positive": sentiment.get("positive_words"),
                "negative": sentiment.get("negative_words")
            })

    return trend


def extract_market_performance(snapshots: List[Dict]) -> Dict[str, Any]:
    """
    Extrae el rendimiento semanal de los principales activos.
    Compara el primer y último snapshot de la semana.
    """
    if len(snapshots) < 2:
        return {}

    first = snapshots[0]
    last = snapshots[-1]

    performance = {}

    # Índices principales
    indices = {
        "^GSPC": "S&P 500",
        "^IXIC": "NASDAQ",
        "^DJI": "Dow Jones",
        "^IPSA": "IPSA Chile"
    }

    for symbol, name in indices.items():
        first_data = first.get("equity", {}).get(symbol, {})
        last_data = last.get("equity", {}).get(symbol, {})

        if first_data.get("close") and last_data.get("close"):
            first_close = first_data["close"]
            last_close = last_data["close"]
            weekly_change = ((last_close / first_close) - 1) * 100

            performance[name] = {
                "start": first_close,
                "end": last_close,
                "weekly_change": round(weekly_change, 2)
            }

    # Chile específico
    first_chile = first.get("chile", {})
    last_chile = last.get("chile", {})

    # IPSA desde chile
    if first_chile.get("ipsa", {}).get("close") and last_chile.get("ipsa", {}).get("close"):
        first_ipsa = first_chile["ipsa"]["close"]
        last_ipsa = last_chile["ipsa"]["close"]
        performance["IPSA"] = {
            "start": first_ipsa,
            "end": last_ipsa,
            "weekly_change": round(((last_ipsa / first_ipsa) - 1) * 100, 2)
        }

    # Dólar observado
    if first_chile.get("dolar_observado", {}).get("value") and last_chile.get("dolar_observado", {}).get("value"):
        first_dolar = first_chile["dolar_observado"]["value"]
        last_dolar = last_chile["dolar_observado"]["value"]
        performance["USD/CLP (Obs)"] = {
            "start": first_dolar,
            "end": last_dolar,
            "weekly_change": round(((last_dolar / first_dolar) - 1) * 100, 2)
        }

    # Commodities
    commodities = {
        "GC=F": "Oro",
        "HG=F": "Cobre",
        "CL=F": "Petróleo WTI"
    }

    for symbol, name in commodities.items():
        first_data = first.get("commodities", {}).get(symbol, {})
        last_data = last.get("commodities", {}).get(symbol, {})

        first_price = first_data.get("close") or first_data.get("price")
        last_price = last_data.get("close") or last_data.get("price")

        if first_price and last_price:
            weekly_change = ((last_price / first_price) - 1) * 100
            performance[name] = {
                "start": first_price,
                "end": last_price,
                "weekly_change": round(weekly_change, 2)
            }

    return performance


def extract_key_news_by_category(snapshots: List[Dict]) -> Dict[str, List[str]]:
    """Agrupa las noticias más importantes por categoría"""
    news_by_category = defaultdict(list)
    seen_headlines = set()

    for snapshot in snapshots:
        news_curated = snapshot.get("news_curated", {})
        curated_newsletters = news_curated.get("curated_newsletters", {})

        for nl_key, nl_data in curated_newsletters.items():
            if "curated" not in nl_data:
                continue

            for news in nl_data["curated"].get("key_news", []):
                headline = news.get("headline", "")
                category = news.get("category", "Otros")
                importance = news.get("importance", "Low")

                # Solo High importance y evitar duplicados
                if importance == "High" and headline not in seen_headlines:
                    seen_headlines.add(headline)
                    news_by_category[category].append({
                        "headline": headline,
                        "summary": news.get("summary", ""),
                        "date": snapshot.get("_date")
                    })

    return dict(news_by_category)


def generate_tactical_ideas(performance: Dict, hot_topics: Dict, sentiment_trend: List) -> str:
    """
    Genera ideas tácticas basadas en el análisis semanal.
    Esta es una sección especial que el usuario pidió enfatizar.
    """
    ideas = []

    # Analizar rendimiento
    winners = []
    losers = []

    for asset, data in performance.items():
        change = data.get("weekly_change", 0)
        if change > 2:
            winners.append((asset, change))
        elif change < -2:
            losers.append((asset, change))

    winners.sort(key=lambda x: x[1], reverse=True)
    losers.sort(key=lambda x: x[1])

    # Construir texto de ideas
    if winners:
        ideas.append(f"**Activos con momentum positivo:** {', '.join([f'{w[0]} (+{w[1]:.1f}%)' for w in winners[:3]])}")

    if losers:
        ideas.append(f"**Activos bajo presión:** {', '.join([f'{l[0]} ({l[1]:.1f}%)' for l in losers[:3]])}")

    # Analizar sentimiento
    if sentiment_trend:
        positive_days = sum(1 for s in sentiment_trend if s.get("sentiment") == "Positivo")
        negative_days = sum(1 for s in sentiment_trend if s.get("sentiment") == "Negativo")

        if positive_days > negative_days:
            ideas.append(f"**Sentimiento semanal:** Predominantemente positivo ({positive_days} sesiones positivas vs {negative_days} negativas)")
        elif negative_days > positive_days:
            ideas.append(f"**Sentimiento semanal:** Predominantemente negativo ({negative_days} sesiones negativas vs {positive_days} positivas)")
        else:
            ideas.append("**Sentimiento semanal:** Mixto/Neutral")

    # Hot topics como catalizadores
    if hot_topics:
        top_3 = list(hot_topics.items())[:3]
        ideas.append(f"**Temas dominantes:** {', '.join([f'{t[0]} ({t[1]} menciones)' for t in top_3])}")

    return "\n".join(ideas)


# ============================================================================
# CONSTRUCCIÓN DEL CONTEXTO
# ============================================================================

def get_contexto_temporal_semanal(start_date: date, end_date: date) -> str:
    """
    Genera contexto temporal para el reporte semanal.
    Indica si es la semana actual, pasada, etc.
    """
    hoy = date.today()
    weekday = hoy.weekday()

    # Fechas formateadas
    inicio_fmt = f"{DIAS_SEMANA[start_date.weekday()]} {start_date.day} de {MESES[start_date.month]}"
    fin_fmt = f"{DIAS_SEMANA[end_date.weekday()]} {end_date.day} de {MESES[end_date.month]}"

    # Determinar si es semana actual o pasada
    dias_desde_fin = (hoy - end_date).days

    if dias_desde_fin <= 2:  # Viernes, Sábado o Domingo de la misma semana
        return f"""**CONTEXTO TEMPORAL:**
- Este reporte cubre la semana que acaba de terminar: {inicio_fmt} al {fin_fmt}.
- Usa "esta semana" para referirte al período analizado.
- Los mercados cerraron el viernes {end_date.day} de {MESES[end_date.month]}."""
    else:
        return f"""**CONTEXTO TEMPORAL:**
- Este reporte cubre la semana pasada: {inicio_fmt} al {fin_fmt}.
- Usa "la semana pasada" para referirte al período analizado.
- Los mercados cerraron el viernes {end_date.day} de {MESES[end_date.month]}."""


def build_weekly_context(snapshots: List[Dict], start_date: date, end_date: date) -> str:
    """Construye el contexto completo para el reporte semanal"""

    week_num = get_week_number(start_date)
    contexto_temporal = get_contexto_temporal_semanal(start_date, end_date)

    parts = []
    parts.append(f"# DATOS SEMANALES - Semana {week_num} ({start_date.isoformat()} al {end_date.isoformat()})")
    parts.append(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    parts.append("")
    parts.append(contexto_temporal)
    parts.append("")

    # 1. Rendimiento semanal
    performance = extract_market_performance(snapshots)
    if performance:
        parts.append("## RENDIMIENTO SEMANAL DE ACTIVOS")
        parts.append("")
        for asset, data in performance.items():
            change = data.get("weekly_change", 0)
            sign = "+" if change >= 0 else ""
            parts.append(f"- **{asset}**: {data['start']:,.2f} → {data['end']:,.2f} ({sign}{change:.2f}%)")
        parts.append("")

    # 2. Hot topics
    hot_topics = extract_hot_topics(snapshots)
    if hot_topics:
        parts.append("## TEMAS MÁS MENCIONADOS EN LA SEMANA")
        parts.append("")
        for topic, count in list(hot_topics.items())[:15]:
            parts.append(f"- {topic}: {count} menciones")
        parts.append("")

    # 3. Evolución del sentimiento
    sentiment_trend = extract_sentiment_trend(snapshots)
    if sentiment_trend:
        parts.append("## EVOLUCIÓN DEL SENTIMIENTO")
        parts.append("")
        for s in sentiment_trend:
            parts.append(f"- {s['date']} ({s['mode']}): {s['sentiment']} (score: {s.get('score', 'N/A')})")
        parts.append("")

    # 4. Ideas tácticas (sección especial)
    parts.append("## IDEAS TÁCTICAS DE LA SEMANA")
    parts.append("")
    tactical = generate_tactical_ideas(performance, hot_topics, sentiment_trend)
    parts.append(tactical)
    parts.append("")

    # 5. Noticias clave por categoría
    news_by_cat = extract_key_news_by_category(snapshots)
    if news_by_cat:
        parts.append("## NOTICIAS CLAVE POR CATEGORÍA")
        parts.append("")

        # Orden de prioridad
        priority = ["Mercados/RV", "Macro", "Geopolítica", "Tech/IA", "Chile", "Commodities", "Corporativo"]

        for category in priority:
            if category in news_by_cat:
                parts.append(f"### {category}")
                for news in news_by_cat[category][:5]:
                    parts.append(f"- **{news['headline']}** ({news['date']})")
                    if news.get('summary'):
                        parts.append(f"  {news['summary'][:200]}...")
                parts.append("")

        # Otras categorías
        for category, news_list in news_by_cat.items():
            if category not in priority:
                parts.append(f"### {category}")
                for news in news_list[:3]:
                    parts.append(f"- **{news['headline']}** ({news['date']})")
                parts.append("")

    # 6. Datos de Chile (último snapshot)
    if snapshots:
        last = snapshots[-1]
        chile = last.get("chile", {})

        parts.append("## DATOS CHILE (Último día)")
        parts.append("")

        if chile.get("ipsa"):
            ipsa = chile["ipsa"]
            parts.append(f"- **IPSA**: {ipsa.get('close', 'N/A')} (1D: {ipsa.get('change_1d', 'N/A')}%, MTD: {ipsa.get('change_mtd', 'N/A')}%, YTD: {ipsa.get('change_ytd', 'N/A')}%)")

        if chile.get("dolar_observado"):
            dolar = chile["dolar_observado"]
            parts.append(f"- **Dólar Observado**: ${dolar.get('value', 'N/A')} ({dolar.get('peso_direction', '')})")

        if chile.get("uf"):
            parts.append(f"- **UF**: ${chile['uf'].get('value', 'N/A')}")

        if chile.get("tpm"):
            parts.append(f"- **TPM**: {chile['tpm'].get('value', 'N/A')}%")

        parts.append("")

    # 7. Resumen de newsletters (condensado)
    parts.append("## FUENTES PROCESADAS")
    parts.append("")

    newsletter_count = 0
    for snapshot in snapshots:
        newsletters = snapshot.get("newsletters", {})
        for key, nl in newsletters.items():
            if nl and isinstance(nl, dict) and nl.get("raw_text"):
                newsletter_count += 1

    parts.append(f"- Total newsletters procesadas: {newsletter_count}")
    parts.append(f"- Snapshots diarios: {len(snapshots)}")
    parts.append("")

    return "\n".join(parts)


# ============================================================================
# GENERACIÓN DEL REPORTE
# ============================================================================

def load_weekly_prompt() -> str:
    """Carga el prompt semanal desde archivo"""
    if os.path.exists(WEEKLY_PROMPT_FILE):
        with open(WEEKLY_PROMPT_FILE, 'r', encoding='utf-8') as f:
            return f.read()

    # Prompt por defecto si no existe el archivo
    return """Genera un informe semanal de mercados profesional.

Incluye:
1. Resumen ejecutivo con los 5-6 hechos clave
2. Chile: IPSA, dólar, cobre, TPM, noticias destacadas
3. Mercados globales: USA, Europa, Asia
4. Commodities: Cobre, Petróleo, Oro
5. Renta fija: Treasuries, spreads
6. Ideas tácticas de la semana
7. Calendario próxima semana
8. Conclusiones estratégicas
9. Glosario

Tono: Profesional, claro, orientado a la acción.
Extensión: 1,200-1,800 palabras."""


def generate_weekly_report_with_anthropic(context: str, prompt: str, week_num: int) -> str:
    """Genera el reporte usando Anthropic Claude"""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY no encontrada en .env")

    client = Anthropic(api_key=api_key)

    print(f"\n[INFO] Generando reporte semanal con Claude (Semana {week_num})...")

    system_prompt = """Eres el Chief Investment Strategist de Grey Bark Advisors.
Tu tarea es crear informes semanales de mercados profesionales, claros y orientados a la acción.

REGLAS:
- NO inventes datos - usa solo lo que está en el contexto
- Mantén Chile al centro del análisis
- Conecta eventos globales con impacto local
- Las ideas tácticas deben ser específicas y accionables
- Incluye siempre el glosario al final"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": f"{prompt}\n\n---\n\nDATOS DE LA SEMANA:\n{context}"
            }
        ]
    )

    return response.content[0].text


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Función principal"""
    print("\n" + "="*80)
    print("GREY BARK ADVISORS - GENERADOR DE REPORTE SEMANAL")
    print("="*80)

    # Determinar fechas de la semana
    if len(sys.argv) > 1:
        # Fecha de referencia específica
        ref_date = date.fromisoformat(sys.argv[1])
    else:
        ref_date = date.today()

    start_date, end_date = get_week_dates(ref_date)
    week_num = get_week_number(start_date)

    print(f"\n[INFO] Semana {week_num}: {format_date_spanish(start_date)} al {format_date_spanish(end_date)}")

    # Cargar snapshots
    snapshots = load_weekly_snapshots(start_date, end_date)

    if not snapshots:
        print("\n[ERROR] No se encontraron snapshots para esta semana.")
        print(f"Verifica que existan archivos en: {HISTORY_DIR}/")
        print("Formato esperado: daily_market_snapshot_YYYY-MM-DD_AM.json")
        return 1

    # Construir contexto
    print("\n[INFO] Analizando datos de la semana...")
    context = build_weekly_context(snapshots, start_date, end_date)

    # Cargar prompt
    prompt = load_weekly_prompt()

    # Generar reporte
    report = generate_weekly_report_with_anthropic(context, prompt, week_num)

    # Guardar
    today = date.today()
    filename = f"weekly_report_semana_{week_num}_{today.isoformat()}.md"

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n[OK] Reporte guardado: {filename}")

    # También guardar en html_out para distribución
    html_out_dir = "html_out"
    os.makedirs(html_out_dir, exist_ok=True)

    html_filename = os.path.join(html_out_dir, f"weekly_report_semana_{week_num}_{today.isoformat()}.md")
    with open(html_filename, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"[OK] Copia en: {html_filename}")

    print("\n" + "="*80)
    print("REPORTE SEMANAL GENERADO EXITOSAMENTE")
    print("="*80)

    return 0


if __name__ == "__main__":
    exit(main())
