# -*- coding: utf-8 -*-
"""
NEWSLETTER CURATOR - ENHANCED V2
Mejoras:
- Detección de temas repetidos cross-newsletter
- Boost de importancia por frecuencia
- Categorías ajustadas para 2026 (Geopolítica e IA críticas)
- Scoring inteligente antes de clasificación
"""

# Proteccion de encoding para Windows (evita errores con emojis)
import sys
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

import os
import json
from typing import Dict, Any, Optional, List
from anthropic import Anthropic
from collections import Counter

def get_anthropic_client() -> Optional[Anthropic]:
    """Obtiene cliente de Anthropic"""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("  ✗ ANTHROPIC_API_KEY not found in .env")
        return None
    
    return Anthropic(api_key=api_key)


def curate_newsletter_enhanced(raw_text: str, source: str, subject: str) -> Dict[str, Any]:
    """
    Estructura un newsletter con categorización mejorada para 2026
    
    PRIORIDADES 2026:
    - Geopolítica (trade wars, conflictos, elecciones) = Macro
    - IA/Tech = Macro
    - Política monetaria = Macro
    """
    client = get_anthropic_client()
    if not client:
        return {"error": "No API key"}
    
    text_limited = raw_text[:10000]
    
    prompt = f"""Analiza este newsletter financiero con enfoque en PRIORIDADES 2026 para gestores de inversión.

NEWSLETTER: {source}
SUBJECT: {subject}

CONTEXTO 2026 - PRIORIDADES PARA GESTORES DE INVERSIÓN:
ESTE ES UN INFORME DE MERCADOS - Los ACTIVOS FINANCIEROS son lo más importante.

JERARQUÍA DE IMPORTANCIA:
1. ACTIVOS FINANCIEROS (RV, RF, Crypto, FX, Commodities)
   - Movimientos de precios, volatilidad, flujos
   - Earnings, valuaciones
   - Cambios en yields, spreads
   
2. MACRO (solo si impacta activos directamente)
   - Tasas de interés, inflación
   - Datos económicos que mueven mercados
   
3. GEOPOLÍTICA (solo si impacta mercados)
   - Aranceles, sanciones con efecto en precios
   - Conflictos que afectan commodities
   
4. TECH/IA (solo si impacta valuaciones o productividad macro)

INSTRUCCIONES:

1. RESUMEN EJECUTIVO (2-3 líneas):
   - Síntesis del mensaje principal
   - Enfocado en lo que impacta decisiones de inversión

2. NOTICIAS PRINCIPALES (5-8 noticias):
   Para cada noticia:
   
   a) headline: Titular conciso (máx 100 caracteres)
   
   b) summary: Resumen de 1-2 líneas con contexto
   
   c) importance: "High" / "Medium" / "Low"
      HIGH si cumple UNO de estos (ORDEN DE PRIORIDAD):
      
      ACTIVOS FINANCIEROS (Prioridad #1):
      - Movimientos significativos de precio (>3% en índices, >5% en activos individuales)
      - Earnings beats/misses con impacto en valuación
      - Cambios en yields de bonos (>10bps)
      - Movimientos FX importantes (>2% en majors)
      - Volatilidad extrema (VIX +20%, eventos de liquidez)
      - Flujos de capital significativos (ETFs, institucionales)
      
      MACRO (solo si mueve activos):
      - Decisiones de tasas de bancos centrales
      - Datos de inflación/empleo que cambian expectativas
      - Política fiscal con impacto directo en bonos/equity
      
      GEOPOLÍTICA (solo si mueve mercados):
      - Aranceles/sanciones con impacto cuantificable
      - Conflictos que afectan commodities (energía, metales)
      
      CORPORATIVO:
      - M&A >$10B
      - Cambios estructurales de industria con impacto en valuaciones
      
      MEDIUM:
      - Noticias macro sin impacto inmediato en precios
      - Corporativo relevante pero sin movimiento de activo
      - Geopolítica sin impacto claro en mercados
      
      LOW:
      - Informativas sin relación con activos
   
   d) category: UNA categoría (PRIORIDAD A MERCADOS/ACTIVOS)
      * "Mercados/RV" - Equity, índices, acciones individuales, volatilidad, flujos
      * "Mercados/RF" - Bonos, yields, spreads, crédito
      * "Mercados/FX" - Divisas, tipo de cambio
      * "Mercados/Crypto" - Criptomonedas, blockchain con impacto financiero
      * "Commodities" - Petróleo, metales, materias primas
      * "Macro" - Tasas centrales, inflación, PIB, empleo (SOLO si mueve activos)
      * "Geopolítica" - Aranceles, conflictos, sanciones (SOLO si impacta mercados)
      * "Corporativo" - M&A, earnings, estrategia
      * "Tech/IA" - Tecnología (SOLO si impacta valuaciones o productividad)
   
   e) data_points: Números clave (precios, %, montos)
   
   f) keywords: 2-4 palabras clave para detección de temas repetidos
      Ej: ["China", "aranceles"], ["Fed", "tasas"], ["Nvidia", "IA"]

3. TENDENCIAS (2-4 tendencias):
   - Patrones o temas recurrentes
   - Conectar noticias relacionadas

4. SENTIMENT:
   - label: "Bullish" / "Somewhat Bullish" / "Neutral" / "Somewhat Bearish" / "Bearish"
   - reason: Justificación

FORMATO JSON:
{{
  "executive_summary": "...",
  "key_news": [
    {{
      "headline": "...",
      "summary": "...",
      "importance": "High|Medium|Low",
      "category": "Mercados/RV|Mercados/RF|Mercados/FX|Mercados/Crypto|Commodities|Macro|Geopolítica|Corporativo|Tech/IA",
      "data_points": ["..."],
      "keywords": ["keyword1", "keyword2"]
    }}
  ],
  "trends": ["..."],
  "sentiment": {{"label": "...", "reason": "..."}}
}}

NEWSLETTER TEXT:
{text_limited}

Responde SOLO con JSON válido."""

    try:
        print(f"  Curating {source}...")
        
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3500,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response_text = response.content[0].text.strip()
        
        # Limpiar markdown
        if response_text.startswith("```json"):
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif response_text.startswith("```"):
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        curated = json.loads(response_text)
        
        # Validar
        required_keys = ["executive_summary", "key_news", "trends", "sentiment"]
        if not all(key in curated for key in required_keys):
            return {"error": "Invalid structure"}
        
        # Stats
        news_count = len(curated['key_news'])
        high_importance = sum(1 for n in curated['key_news'] if n.get('importance') == 'High')
        trends_count = len(curated['trends'])
        
        print(f"  ✓ Curated: {news_count} news ({high_importance} high priority), {trends_count} trends")
        
        return curated
        
    except Exception as e:
        print(f"  ✗ Error curating: {e}")
        return {"error": str(e)}


def analyze_cross_newsletter_patterns(all_curated: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analiza patrones CROSS-NEWSLETTER
    
    Lógica:
    - Si un tema aparece en 3+ newsletters → muy importante
    - Si keywords se repiten → tendencia global
    - Boost de importancia por frecuencia
    """
    print("\n" + "="*80)
    print("CROSS-NEWSLETTER ANALYSIS")
    print("="*80)
    
    # Recopilar todos los keywords
    all_keywords = []
    all_news_with_source = []
    
    for newsletter_key, data in all_curated.items():
        if "error" in data or "curated" not in data:
            continue
        
        curated = data["curated"]
        source = data.get("source", newsletter_key)
        
        for news in curated.get("key_news", []):
            keywords = news.get("keywords", [])
            all_keywords.extend(keywords)
            
            all_news_with_source.append({
                "source": source,
                "headline": news.get("headline"),
                "keywords": keywords,
                "category": news.get("category"),
                "original_importance": news.get("importance")
            })
    
    # Contar frecuencia de keywords
    keyword_freq = Counter(all_keywords)
    
    print(f"\nTotal keywords: {len(all_keywords)}")
    print(f"Unique keywords: {len(keyword_freq)}")
    
    # Identificar temas HOT (aparecen 3+ veces)
    hot_topics = {kw: count for kw, count in keyword_freq.items() if count >= 3}
    
    if hot_topics:
        print(f"\n🔥 HOT TOPICS (3+ menciones):")
        for topic, count in sorted(hot_topics.items(), key=lambda x: x[1], reverse=True):
            print(f"  • {topic}: {count} menciones")
    
    # Agrupar noticias por tema repetido
    topic_clusters = {}
    for topic in hot_topics.keys():
        related_news = [
            n for n in all_news_with_source 
            if topic.lower() in [k.lower() for k in n["keywords"]]
        ]
        if related_news:
            topic_clusters[topic] = related_news
    
    # Generar insights
    insights = {
        "hot_topics": hot_topics,
        "topic_clusters": topic_clusters,
        "recommendations": []
    }
    
    # Recommendations basadas en frecuencia
    for topic, count in sorted(hot_topics.items(), key=lambda x: x[1], reverse=True):
        cluster = topic_clusters.get(topic, [])
        sources = list(set([n["source"] for n in cluster]))
        
        if count >= 5:
            priority = "CRÍTICO"
        elif count >= 3:
            priority = "ALTO"
        else:
            priority = "MEDIO"
        
        insights["recommendations"].append({
            "topic": topic,
            "frequency": count,
            "priority": priority,
            "sources": sources[:3],  # Top 3 fuentes
            "action": f"Tema repetido en {count} newsletters - elevar a importancia HIGH"
        })
    
    print(f"\n📊 RECOMMENDATIONS:")
    for rec in insights["recommendations"]:
        print(f"  {rec['priority']}: {rec['topic']} ({rec['frequency']} menciones)")
        print(f"    → {rec['action']}")
        print(f"    Fuentes: {', '.join(rec['sources'])}")
    
    return insights


def boost_importance_by_frequency(all_curated: Dict[str, Any], insights: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ajusta importancia de noticias basado en frecuencia cross-newsletter
    
    Regla: Si un tema aparece en 3+ newsletters → boost a High
    """
    print("\n" + "="*80)
    print("IMPORTANCE BOOSTING")
    print("="*80)
    
    hot_topics = insights.get("hot_topics", {})
    boosted_count = 0
    
    for newsletter_key, data in all_curated.items():
        if "error" in data or "curated" not in data:
            continue
        
        curated = data["curated"]
        
        for news in curated.get("key_news", []):
            keywords = news.get("keywords", [])
            original_importance = news.get("importance")
            
            # Check si algún keyword es hot topic
            for kw in keywords:
                if kw in hot_topics and hot_topics[kw] >= 3:
                    # Boost a High si no lo era
                    if original_importance != "High":
                        news["importance"] = "High"
                        news["boosted"] = True
                        news["boost_reason"] = f"Tema repetido: '{kw}' ({hot_topics[kw]} menciones)"
                        boosted_count += 1
                        print(f"  ↑ BOOST: '{news['headline'][:50]}...' → High (keyword: {kw})")
                        break
    
    print(f"\nTotal noticias con boost: {boosted_count}")
    
    return all_curated


def curate_all_newsletters_enhanced(newsletters_raw: Dict[str, Any], df_resumen_raw: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Procesa todos los newsletters + DF Resumen + WSJ PDF con análisis cross-newsletter
    
    Args:
        newsletters_raw: Dict con newsletters raw del JSON
        df_resumen_raw: Dict con DF Resumen raw (opcional)
    
    Returns:
        Dict con todo curado + estadísticas agregadas
    """
    print("\n" + "="*80)
    print("NEWSLETTER CURATION - ENHANCED V2 (2026 Edition)")
    print("="*80)
    print("\nPRIORIDADES 2026:")
    print("  📈 Activos Financieros = #1 Prioridad")
    print("  💰 Macro (si mueve activos) = #2")
    print("  🌍 Geopolítica (si impacta mercados) = #3")
    print("="*80)
    
    # FASE 1: Consolidar todas las fuentes
    all_sources = {}
    
    # 1A. Newsletters regulares
    for key, newsletter_data in newsletters_raw.items():
        if newsletter_data is None:
            continue
        
        # WSJ PDF tiene 'full_text' en vez de 'raw_text'
        if key == "wsj_pdf":
            raw_text = newsletter_data.get("full_text", "")
        else:
            raw_text = newsletter_data.get("raw_text", "")
        
        if not raw_text:
            continue
        
        all_sources[key] = {
            "source": newsletter_data.get("source", key),
            "subject": newsletter_data.get("subject", ""),
            "raw_text": raw_text
        }
    
    # 1B. DF Resumen (si existe)
    if df_resumen_raw and df_resumen_raw.get("raw_text"):
        all_sources["df_resumen"] = {
            "source": "Diario Financiero Resumen",
            "subject": f"Edición {df_resumen_raw.get('edition_date', '')}",
            "raw_text": df_resumen_raw["raw_text"]
        }
        print(f"\n[INFO] DF Resumen agregado ({len(df_resumen_raw['raw_text'])} chars)")
    
    print(f"\n[INFO] Total fuentes a procesar: {len(all_sources)}")
    for key in all_sources.keys():
        source_name = all_sources[key]["source"]
        text_len = len(all_sources[key]["raw_text"])
        print(f"  • {source_name}: {text_len:,} chars")
    
    # FASE 2: Curar cada fuente
    curated = {}
    
    for key, source_data in all_sources.items():
        source = source_data["source"]
        subject = source_data["subject"]
        raw_text = source_data["raw_text"]
        
        print(f"\n→ {source}")
        
        curated_data = curate_newsletter_enhanced(raw_text, source, subject)
        
        if "error" not in curated_data:
            curated[key] = {
                "source": source,
                "subject": subject,
                "curated": curated_data
            }
        else:
            curated[key] = {
                "source": source,
                "subject": subject,
                "error": curated_data["error"]
            }
    
    # FASE 2: Análisis cross-newsletter
    insights = analyze_cross_newsletter_patterns(curated)
    
    # FASE 3: Boost de importancia
    curated = boost_importance_by_frequency(curated, insights)
    
    # FASE 4: Estadísticas finales
    stats = {
        "total_newsletters": len(curated),
        "total_news": 0,
        "high_importance_news": 0,
        "categories": {},
        "hot_topics": insights.get("hot_topics", {})
    }
    
    for data in curated.values():
        if "curated" in data:
            for news in data["curated"].get("key_news", []):
                stats["total_news"] += 1
                if news.get("importance") == "High":
                    stats["high_importance_news"] += 1
                
                cat = news.get("category", "Unknown")
                stats["categories"][cat] = stats["categories"].get(cat, 0) + 1
    
    print("\n" + "="*80)
    print("FINAL STATISTICS")
    print("="*80)
    print(f"\nNewsletters: {stats['total_newsletters']}")
    print(f"Total news: {stats['total_news']}")
    print(f"High importance: {stats['high_importance_news']} ({stats['high_importance_news']/stats['total_news']*100:.0f}%)")
    
    print(f"\nBy category:")
    for cat, count in sorted(stats['categories'].items(), key=lambda x: x[1], reverse=True):
        print(f"  {cat}: {count}")
    
    return {
        "curated_newsletters": curated,
        "cross_newsletter_insights": insights,
        "statistics": stats
    }


# ==============================================================================
# TEST
# ==============================================================================

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    print("="*80)
    print("TEST - ENHANCED CURATOR V2")
    print("="*80)
    
    # Simular 3 newsletters con temas repetidos
    test_newsletters = {
        "wsj_1": {
            "source": "WSJ Markets",
            "subject": "China Trade War Escalates",
            "raw_text": "China announced new tariffs on US goods. Trade tensions escalate. Tech sector impacted. Nvidia warns of supply chain disruptions. Markets fell 2% on the news."
        },
        "ft_1": {
            "source": "FT Markets",
            "subject": "Geopolitical Risks Rise",
            "raw_text": "US-China trade war intensifies. European markets decline. Nvidia stock drops 5% on China concerns. Fed watches inflation impact from tariffs."
        },
        "bloomberg_1": {
            "source": "Bloomberg Brief",
            "subject": "Tech Under Pressure",
            "raw_text": "Nvidia faces China headwinds. AI chip exports restricted. Trade war impacts semiconductor sector. Fed signals patience on rate cuts."
        }
    }
    
    result = curate_all_newsletters_enhanced(test_newsletters)
    
    print("\n" + "="*80)
    print("RESULT - TOP PRIORITIES")
    print("="*80)
    
    # Mostrar solo noticias HIGH importance
    for key, data in result["curated_newsletters"].items():
        if "curated" in data:
            high_news = [n for n in data["curated"]["key_news"] if n.get("importance") == "High"]
            if high_news:
                print(f"\n{data['source']}:")
                for news in high_news:
                    boost_icon = " 🔥" if news.get("boosted") else ""
                    print(f"  • [{news['category']}] {news['headline']}{boost_icon}")
                    if news.get("boost_reason"):
                        print(f"    Reason: {news['boost_reason']}")
