"""GreyBark Curator (AM/PM)

Objetivo:
- Transformar el snapshot "raw" (daily_market_snapshot*.json) en un JSON curado con:
  - jerarquía editorial
  - pre-síntesis determinística (drivers del día)
  - tablas determinísticas
  - buckets: Resumen Ejecutivo, Economía, Política/Geopolítica, Chile/LatAm, Activos

Principio:
- Determinístico (sin LLM).
- Auditabilidad: cada titular tiene tag/bucket/score/fuente.

Notas:
- El LLM debe recibir el curated snapshot (no el raw) y actuar como ANALISTA/REDACCIÓN.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

TZ_DEFAULT = "America/Santiago"

# ----------------------------
# Headline models
# ----------------------------

@dataclass
class Headline:
    source: str
    title: str
    published_local: Optional[str] = None  # "YYYY-MM-DD HH:MM"
    url: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None

@dataclass
class RankedHeadline(Headline):
    tag: str = "unknown"
    bucket: str = "activos"
    region: str = "Global"
    asset_relevance: str = "multi_asset"
    score: int = 0

# Buckets editoriales
BUCKET_RESUMEN = "resumen_ejecutivo"
BUCKET_ECONOMIA = "economia"
BUCKET_POLITICA = "politica_geopolitica"
BUCKET_CHILE = "chile_latam"
BUCKET_ACTIVOS = "activos"

# Tags (temas)
TAG_NOISE = "noise"
TAG_MONETARY = "monetary_policy"
TAG_MACRO = "macro_data"
TAG_RATES = "rates_bonds"
TAG_EQUITY = "equity_index"
TAG_COM_ENERGY = "commodities_energy"
TAG_COM_METALS = "commodities_metals"
TAG_FX_USD = "fx_usd"
TAG_GEO = "geopolitics"
TAG_CHILE = "chile_local"
TAG_LATAM = "latam"
TAG_COMPANY = "company_idiosyncratic"

# Keywords simples (ampliables)
KW = {
    TAG_CHILE: [
        "chile", "ipsa", "bcch", "banco central de chile", "peso chileno", "dólar observado",
        "ministerio de hacienda", "imacec", "uf",
    ],
    TAG_LATAM: [
        "brazil", "mexico", "argentina", "peru", "colombia", "latam", "latin america",
    ],
    TAG_MONETARY: [
        "fed", "powell", "ecb", "lagarde", "boe", "bank of england", "central bank",
        "rate cut", "rate hike", "policy rate", "fomc", "tpm", "banco central",
    ],
    TAG_MACRO: [
        "unemployment", "jobs", "payroll", "inflation", "cpi", "pce", "ppi", "gdp", "pmi",
        "retail sales", "growth", "activity", "imacec", "ipc",
    ],
    TAG_RATES: [
        "treasury", "yield", "curve", "spread", "credit", "bond", "duration", "10-year", "2-year",
    ],
    TAG_COM_ENERGY: [
        "oil", "wti", "brent", "gas", "opec", "crude",
    ],
    TAG_COM_METALS: [
        "copper", "gold", "silver", "metals",
    ],
    TAG_FX_USD: [
        "dollar", "dxy", "fx", "usd", "eur", "yen", "gbp", "currency",
    ],
    TAG_EQUITY: [
        "stocks", "equities", "s&p", "nasdaq", "dow", "stoxx", "dax", "ftse", "nikkei", "msci",
        "earnings", "guidance",
    ],
    TAG_GEO: [
        "ukraine", "russia", "china", "taiwan", "israel", "gaza", "sanction", "geopolit",
        "election", "elections", "congress", "shutdown",
    ],
}

NOISE_KW = [
    "murder", "killed", "celebrity", "trader joe", "fashion", "lifestyle", "quiz",
    "shooting", "knife", "engaged", "boots",
]

# Base score por tag (determinístico)
BASE_TAG_SCORE = {
    TAG_CHILE: 45,
    TAG_LATAM: 35,
    TAG_MONETARY: 40,
    TAG_MACRO: 35,
    TAG_RATES: 30,
    TAG_EQUITY: 28,
    TAG_COM_ENERGY: 25,
    TAG_COM_METALS: 23,
    TAG_FX_USD: 22,
    TAG_GEO: 22,
    TAG_COMPANY: 12,
    TAG_NOISE: -999,
}

REGION_BONUS = {"Chile": 15, "LatAm": 10, "Global": 8, "US": 6, "Europe": 4, "Asia": 4}

SOURCE_BONUS = {
    "WSJ_MARKETS_PM": 20,
    "FT_MARKETS": 18,
    "DF_RESUMEN": 18,
    "DF_PRIMER_CLICK": 14,
    "REUTERS": 10,
    "FT": 8,
    "WSJ": 8,
    "CNBC": 6,
    "RSS": 5,
    "OTHER": 3,
}

def _norm(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s

def _today_from_raw(raw: Dict[str, Any]) -> Optional[dt.date]:
    d = raw.get("date")
    if isinstance(d, str) and len(d) >= 10:
        try:
            return dt.datetime.strptime(d[:10], "%Y-%m-%d").date()
        except Exception:
            return None
    return None

def _parse_email_date(value: Any) -> Optional[dt.datetime]:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, str):
        s = value.strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return dt.datetime.strptime(s[:len(fmt)], fmt)
            except Exception:
                pass
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(s).replace(tzinfo=None)
        except Exception:
            return None
    return None

def _dt_to_local_str(dttm: Optional[dt.datetime]) -> Optional[str]:
    if not dttm:
        return None
    return dttm.strftime("%Y-%m-%d %H:%M")

def classify_tag(title: str) -> str:
    t = _norm(title)
    if any(k in t for k in NOISE_KW):
        return TAG_NOISE
    # Chile/LatAm first
    if any(k in t for k in KW[TAG_CHILE]):
        return TAG_CHILE
    if any(k in t for k in KW[TAG_LATAM]):
        return TAG_LATAM
    # Monetary/Macro
    if any(k in t for k in KW[TAG_MONETARY]):
        return TAG_MONETARY
    if any(k in t for k in KW[TAG_MACRO]):
        return TAG_MACRO
    # Rates
    if any(k in t for k in KW[TAG_RATES]):
        return TAG_RATES
    # Commodities
    if any(k in t for k in KW[TAG_COM_ENERGY]):
        return TAG_COM_ENERGY
    if any(k in t for k in KW[TAG_COM_METALS]):
        return TAG_COM_METALS
    # FX
    if any(k in t for k in KW[TAG_FX_USD]):
        return TAG_FX_USD
    # Equity
    if any(k in t for k in KW[TAG_EQUITY]):
        return TAG_EQUITY
    # Geo
    if any(k in t for k in KW[TAG_GEO]):
        return TAG_GEO
    return TAG_COMPANY

def classify_region(title: str, tag: str) -> str:
    t = _norm(title)
    if tag == TAG_CHILE:
        return "Chile"
    if tag == TAG_LATAM:
        return "LatAm"
    if any(k in t for k in ["u.s.", "united states", "fed", "powell", "treasury"]):
        return "US"
    if any(k in t for k in ["europe", "ecb", "stoxx", "dax", "ftse", "uk "]):
        return "Europe"
    if any(k in t for k in ["china", "japan", "nikkei", "asia", "taiwan", "hong kong"]):
        return "Asia"
    return "Global"

def classify_bucket(tag: str) -> str:
    if tag in (TAG_MONETARY, TAG_MACRO, TAG_RATES):
        return BUCKET_ECONOMIA
    if tag in (TAG_GEO,):
        return BUCKET_POLITICA
    if tag in (TAG_CHILE, TAG_LATAM):
        return BUCKET_CHILE
    return BUCKET_ACTIVOS

def classify_asset_relevance(tag: str) -> str:
    if tag in (TAG_MONETARY, TAG_MACRO, TAG_GEO):
        return "multi_asset"
    if tag == TAG_RATES:
        return "rates"
    if tag in (TAG_EQUITY, TAG_COMPANY):
        return "equity"
    if tag in (TAG_COM_ENERGY, TAG_COM_METALS):
        return "commodities"
    if tag == TAG_FX_USD:
        return "fx"
    if tag in (TAG_CHILE, TAG_LATAM):
        return "chile"
    return "multi_asset"

def source_bonus(source: str) -> int:
    s = (source or "").upper()
    for k, v in SOURCE_BONUS.items():
        if k in s:
            return v
    return SOURCE_BONUS["OTHER"]

def recency_bonus(published_local: Optional[str], mode: str, on_date: dt.date) -> int:
    if not published_local:
        return -5 if mode == "PM" else 0
    try:
        dttm = dt.datetime.strptime(published_local, "%Y-%m-%d %H:%M")
    except Exception:
        return -3

    if mode == "PM":
        # referencia: 18:30 del mismo día
        ref = dt.datetime.combine(on_date, dt.time(18, 30))
        delta_h = (ref - dttm).total_seconds() / 3600.0
        if delta_h < 0:
            return -5
        if delta_h <= 2:
            return 10
        if delta_h <= 6:
            return 6
        return 3

    # AM: overnight
    if dttm.date() == on_date and dttm.time() <= dt.time(8, 0):
        return 8
    if dttm.date() == (on_date - dt.timedelta(days=1)) and dttm.time() >= dt.time(19, 0):
        return 8
    return 0

def score_headline(h: Headline, tag: str, region: str, mode: str, on_date: dt.date) -> int:
    if tag == TAG_NOISE:
        return -999
    base = BASE_TAG_SCORE.get(tag, 10)
    reg = REGION_BONUS.get(region, 0)
    src = source_bonus(h.source)
    rec = recency_bonus(h.published_local, mode, on_date)

    t = _norm(h.title)
    if t in ("markets mixed", "stocks mixed", "stocks slip", "markets fall", "markets rise"):
        base -= 8

    return int(base + reg + src + rec)

def _fingerprint(title: str) -> str:
    t = _norm(title)
    t = re.sub(r"\b\d+(\.\d+)?%?\b", "", t)
    t = re.sub(r"[^a-z\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:140]

def dedupe_ranked(items: List[RankedHeadline]) -> List[RankedHeadline]:
    seen = set()
    out: List[RankedHeadline] = []
    for it in sorted(items, key=lambda x: x.score, reverse=True):
        fp = _fingerprint(it.title)
        if fp in seen:
            continue
        seen.add(fp)
        out.append(it)
    return out

def rank_headlines(headlines: List[Headline], mode: str, on_date: dt.date) -> List[RankedHeadline]:
    ranked: List[RankedHeadline] = []
    for h in headlines:
        tag = classify_tag(h.title)
        if tag == TAG_NOISE:
            continue
        region = classify_region(h.title, tag)
        bucket = classify_bucket(tag)
        asset_rel = classify_asset_relevance(tag)
        score = score_headline(h, tag, region, mode, on_date)
        ranked.append(RankedHeadline(**h.__dict__, tag=tag, bucket=bucket, region=region, asset_relevance=asset_rel, score=score))
    ranked = dedupe_ranked(ranked)
    ranked.sort(key=lambda x: x.score, reverse=True)
    return ranked

# ----------------------------
# Tablas determinísticas (close)
# ----------------------------

def _extract_table_rows(raw: Dict[str, Any], section: str) -> List[Dict[str, Any]]:
    block = raw.get(section)
    if isinstance(block, list):
        return [x for x in block if isinstance(x, dict)]
    return []

def _label(it: Dict[str, Any]) -> str:
    for k in ("name", "label", "shortName", "longName"):
        v = it.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    sym = it.get("symbol") or it.get("ticker") or it.get("key")
    return str(sym) if sym else "N/A"

def _key(it: Dict[str, Any]) -> str:
    sym = it.get("symbol") or it.get("ticker") or it.get("key")
    return str(sym) if sym else _label(it)

def _num(it: Dict[str, Any], keys: Tuple[str, ...]) -> Optional[float]:
    for k in keys:
        v = it.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return None

def build_tables(raw: Dict[str, Any]) -> Dict[str, Any]:
    tables: Dict[str, Any] = {"markets_close": {}, "chile_close": {}}

    def map_section(section: str) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for it in _extract_table_rows(raw, section):
            rows.append({
                "key": _key(it),
                "label": _label(it),
                "level": _num(it, ("close", "value", "last", "price", "yield", "rate")),
                "chg_pct_day": _num(it, ("change_pct", "chg_pct", "pct_change", "changePercent")),
                "chg_pct_wtd": _num(it, ("wtd_pct", "wtd", "change_week_pct")),
                "chg_pct_mtd": _num(it, ("mtd_pct", "mtd", "change_month_pct")),
                "chg_pct_ytd": _num(it, ("ytd_pct", "ytd", "change_ytd_pct")),
            })
        return rows

    tables["markets_close"]["indices"] = map_section("equity")
    tables["markets_close"]["rates_bonds"] = map_section("rates_bonds")
    tables["markets_close"]["fx"] = map_section("fx")
    tables["markets_close"]["commodities"] = map_section("commodities")

    # VIX (si viene como equity item ^VIX)
    vix_row = next((r for r in tables["markets_close"]["indices"] if r["key"] in ("^VIX", "VIX")), None)
    tables["markets_close"]["volatility"] = []
    if vix_row:
        tables["markets_close"]["volatility"].append({"key": vix_row["key"], "label": "VIX", "level": vix_row["level"], "chg_pct_day": vix_row["chg_pct_day"]})

    # Chile (en raw suele venir dict)
    chile = raw.get("chile") if isinstance(raw.get("chile"), dict) else {}

    def _ch_obj(name: str) -> Optional[Dict[str, Any]]:
        v = chile.get(name)
        return v if isinstance(v, dict) else None

    ipsa = _ch_obj("ipsa")
    tpm = _ch_obj("tpm")
    uf = _ch_obj("uf")
    dolar_obs = _ch_obj("dolar_observado")

    def _ch_val(obj: Optional[Dict[str, Any]]) -> Optional[float]:
        if not obj:
            return None
        return _num(obj, ("value", "close", "last"))

    tables["chile_close"]["ipsa"] = {
        "level": _ch_val(ipsa),
        "chg_pct_day": _num(ipsa or {}, ("change_pct", "chg_pct", "pct_change")),
        "chg_pct_mtd": _num(ipsa or {}, ("mtd_pct", "mtd")),
        "chg_pct_ytd": _num(ipsa or {}, ("ytd_pct", "ytd")),
        "asof": "close",
    }

    tables["chile_close"]["tpm"] = {
        "level": _ch_val(tpm),
        "asof": "latest",
        "change_expectations": (tpm or {}).get("expectations"),
    }

    obs_value = _ch_val(dolar_obs)
    obs_prev = _num(dolar_obs or {}, ("prev_value", "previous", "prev"))
    peso_interp = None
    if obs_value is not None and obs_prev is not None:
        if obs_value > obs_prev:
            peso_interp = "peso_se_deprecia"
        elif obs_value < obs_prev:
            peso_interp = "peso_se_aprecia"
        else:
            peso_interp = "neutral"

    tables["chile_close"]["dolar"] = {
        "dolar_observado_bcch": {
            "unit": "CLP per USD",
            "value": obs_value,
            "prev_value": obs_prev,
            "change": (obs_value - obs_prev) if (obs_value is not None and obs_prev is not None) else None,
            "change_pct": _num(dolar_obs or {}, ("change_pct", "chg_pct", "pct_change")),
            "peso_interpretation": peso_interp,
            "asof": "BCCh",
        },
        "usdclp_mercado_yahoo": None,
    }

    # Buscar CLP=X en fx
    for r in tables["markets_close"]["fx"]:
        if r["key"] == "CLP=X":
            tables["chile_close"]["dolar"]["usdclp_mercado_yahoo"] = {
                "unit": "CLP per USD",
                "close": r["level"],
                "chg_pct_day": r["chg_pct_day"],
                "chg_pct_mtd": r["chg_pct_mtd"],
                "chg_pct_ytd": r["chg_pct_ytd"],
                "asof": "close",
                "notes": "Yahoo CLP=X",
            }
            break

    tables["chile_close"]["uf"] = {"value": _ch_val(uf), "unit": "CLP", "asof": "BCCh"}
    return tables

# ----------------------------
# Drivers determinísticos desde newsletters
# ----------------------------

def _extract_text_block(nl: Any) -> str:
    if nl is None:
        return ""
    if isinstance(nl, str):
        return nl
    if isinstance(nl, dict):
        for k in ("raw_text", "text", "content", "body", "plain_text"):
            v = nl.get(k)
            if isinstance(v, str) and v.strip():
                return v
    return ""

def extract_wsj_markets_pm_bullets(wsj_nl: Any) -> List[str]:
    txt = _extract_text_block(wsj_nl)
    if not txt:
        return []
    m = re.search(
        r"What Happened in Markets Today\s*(.+?)(CONTENT FROM:|Markets at a Glance|One Big Story|What’s Coming Up|About Us)",
        txt,
        re.DOTALL | re.IGNORECASE,
    )
    block = m.group(1).strip() if m else ""
    if not block:
        block = txt[:1200]

    lines = [re.sub(r"\s+", " ", l).strip(" -•\t") for l in re.split(r"\n{2,}|\n", block) if l.strip()]
    out: List[str] = []
    for l in lines:
        if len(l) < 20:
            continue
        if "CONTENT FROM" in l.upper():
            continue
        out.append(l)
    return out[:6]

def extract_ft_markets_bullets(ft_nl: Any) -> List[str]:
    txt = _extract_text_block(ft_nl)
    if not txt:
        return []
    txt = re.sub(r"https?://\S+", "", txt)
    parts = [p.strip() for p in re.split(r"\n{2,}|\n|- ", txt) if p.strip()]
    out: List[str] = []
    for p in parts:
        if len(p) < 25:
            continue
        if "unsubscribe" in p.lower():
            continue
        out.append(re.sub(r"\s+", " ", p))
    return out[:6]

# ----------------------------
# Curación principal
# ----------------------------

def curate_snapshot(raw: Dict[str, Any], mode: str) -> Dict[str, Any]:
    mode = mode.upper().strip()
    if mode not in ("AM", "PM"):
        raise ValueError("mode debe ser AM o PM")

    on_date = _today_from_raw(raw) or dt.date.today()

    newsletters = raw.get("newsletters") if isinstance(raw.get("newsletters"), dict) else {}
    # Eliminamos Scotiabank por diseño (aunque venga en raw)
    newsletters = {k: v for k, v in newsletters.items() if not k.lower().startswith("scotia")}

    df_resumen = raw.get("df_resumen_diario")
    df_primer_click = newsletters.get("df_primer_click") or newsletters.get("df_primer_click_am") or newsletters.get("df_primer_click_pm")
    wsj_pm = newsletters.get("wsj_markets_pm")
    ft_markets = newsletters.get("ft_markets") or newsletters.get("ft_markets_afternoon") or newsletters.get("ft_markets_evening")

    # 1) Construir pool de titulares (RSS + newsletters como "item")
    pool: List[Headline] = []

    rss = (raw.get("news", {}) or {}).get("rss")
    if isinstance(rss, list):
        for it in rss:
            if not isinstance(it, dict):
                continue
            title = it.get("title")
            if not isinstance(title, str) or not title.strip():
                continue
            pool.append(
                Headline(
                    source=str(it.get("source") or "RSS"),
                    title=title.strip(),
                    published_local=_dt_to_local_str(_parse_email_date(it.get("published"))),
                    url=it.get("link") or it.get("url"),
                    raw=it,
                )
            )

    for key, nl in newsletters.items():
        txt = _extract_text_block(nl)
        if not txt:
            continue
        subj = nl.get("subject") if isinstance(nl, dict) else None
        title = subj.strip() if isinstance(subj, str) and subj.strip() else f"Newsletter: {key}"
        published_local = None
        if isinstance(nl, dict):
            published_local = _dt_to_local_str(_parse_email_date(nl.get("email_date") or nl.get("published") or nl.get("date")))
        pool.append(Headline(source=f"NEWSLETTER:{key}", title=title, published_local=published_local, raw=nl))

    ranked = rank_headlines(pool, mode=mode, on_date=on_date)

    # 2) Support + radar
    support_max = 6
    titulares_support: List[Dict[str, Any]] = []
    radar_by_bucket: Dict[str, List[Dict[str, Any]]] = {BUCKET_ECONOMIA: [], BUCKET_POLITICA: [], BUCKET_CHILE: [], BUCKET_ACTIVOS: []}

    for it in ranked:
        obj = {
            "score": it.score,
            "tag": it.tag,
            "bucket": it.bucket,
            "region": it.region,
            "asset_relevance": it.asset_relevance,
            "source": it.source,
            "title": it.title,
            "published_local": it.published_local,
            "url": it.url,
        }
        if len(titulares_support) < support_max:
            titulares_support.append(obj)
        else:
            # Radar (máx 2 por bucket como MVP)
            if len(radar_by_bucket[it.bucket]) < 2:
                radar_by_bucket[it.bucket].append(obj)

    # 3) Drivers editoriales
    hechos_del_dia: List[Dict[str, Any]] = []
    am_contexto: List[Dict[str, Any]] = []

    if mode == "PM":
        wsj_bul = extract_wsj_markets_pm_bullets(wsj_pm)
        ft_bul = extract_ft_markets_bullets(ft_markets)

        for s in wsj_bul[:4]:
            hechos_del_dia.append({"rank": len(hechos_del_dia) + 1, "topic": "WSJ Markets PM", "summary": s, "sources": ["WSJ_MARKETS_PM"]})
        for s in ft_bul:
            if len(hechos_del_dia) >= 4:
                break
            hechos_del_dia.append({"rank": len(hechos_del_dia) + 1, "topic": "FT Markets", "summary": s, "sources": ["FT_MARKETS"]})

    else:  # AM
        if df_resumen:
            df_txt = _extract_text_block(df_resumen)
            parts = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n{2,}|\n", df_txt) if p.strip()]
            for p in parts[:3]:
                am_contexto.append({"rank": len(am_contexto) + 1, "topic": "DF Resumen Diario", "summary": p, "sources": ["DF_RESUMEN"]})

        wsj_bul = extract_wsj_markets_pm_bullets(wsj_pm)
        for p in wsj_bul[:2]:
            if len(am_contexto) >= 5:
                break
            am_contexto.append({"rank": len(am_contexto) + 1, "topic": "WSJ Markets PM (previo)", "summary": p, "sources": ["WSJ_MARKETS_PM"]})

        if df_primer_click:
            pc_txt = _extract_text_block(df_primer_click)
            parts = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n{2,}|\n", pc_txt) if p.strip()]
            for p in parts[:2]:
                if len(am_contexto) >= 6:
                    break
                am_contexto.append({"rank": len(am_contexto) + 1, "topic": "DF Primer Click", "summary": p, "sources": ["DF_PRIMER_CLICK"]})

    # 4) Resumen ejecutivo: 3-5 bullets desde drivers + fallback a titulares support
    resumen_exec: List[Dict[str, Any]] = []
    if mode == "PM":
        for h in hechos_del_dia[:4]:
            resumen_exec.append({"rank": len(resumen_exec) + 1, "summary": h["summary"], "sources": h["sources"]})
    else:
        for c in am_contexto[:4]:
            resumen_exec.append({"rank": len(resumen_exec) + 1, "summary": c["summary"], "sources": c["sources"]})

    for t in titulares_support:
        if len(resumen_exec) >= 5:
            break
        resumen_exec.append({"rank": len(resumen_exec) + 1, "summary": t["title"], "sources": [t["source"]]})

    # 5) Tablas determinísticas
    tables = build_tables(raw)

    # 6) Buckets editoriales finales (mezcla: Resumen, Economía, Política, Chile/LatAm, Activos)
    buckets = {
        BUCKET_RESUMEN: resumen_exec,
        BUCKET_ECONOMIA: [t for t in titulares_support if t["bucket"] == BUCKET_ECONOMIA][:4],
        BUCKET_POLITICA: [t for t in titulares_support if t["bucket"] == BUCKET_POLITICA][:3],
        BUCKET_CHILE: [t for t in titulares_support if t["bucket"] == BUCKET_CHILE][:4],
        BUCKET_ACTIVOS: {
            "equity": [t for t in titulares_support if t["asset_relevance"] == "equity"][:3],
            "rates": [t for t in titulares_support if t["asset_relevance"] == "rates"][:3],
            "fx": [t for t in titulares_support if t["asset_relevance"] == "fx"][:3],
            "commodities": [t for t in titulares_support if t["asset_relevance"] == "commodities"][:3],
        },
    }

    editorial_core: Dict[str, Any] = {
        "buckets": buckets,
        "titulares_support": titulares_support,
        "titulares_radar": radar_by_bucket,
    }
    if mode == "PM":
        editorial_core["hechos_del_dia"] = hechos_del_dia
    else:
        editorial_core["am_contexto_editorial"] = am_contexto

    curated = {
        "meta": {
            "date": on_date.isoformat(),
            "report_type": mode,
            "timezone": TZ_DEFAULT,
            "generated_at_local": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "window_local": {"start": "08:00", "end": "18:30"} if mode == "PM" else None,
            "data_policy": {"no_inventar_datos": True},
        },
        "source_status": {
            "df_resumen_diario": {"available": bool(df_resumen), "asof": None, "notes": None},
            "wsj_markets_pm": {"available": bool(wsj_pm), "asof": None, "notes": None},
            "df_primer_click": {"available": bool(df_primer_click), "asof": None, "notes": None},
            "ft_markets": {"available": bool(ft_markets), "asof": None, "notes": None},
        },
        "editorial_core": editorial_core,
        "tables": tables,
        "llm_instructions_hints": {
            "must_use": ["editorial_core.buckets", "tables"],
            "avoid": [
                "Inventar catalizadores",
                "Narrar tabla completa en texto",
                "Mezclar dólar observado con CLP=X",
            ],
            "tone": "research",
        },
    }
    return curated
