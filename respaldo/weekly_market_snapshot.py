import os
import json
import glob
import re
import sys
import imaplib
import email
from email.header import decode_header
from html import unescape
from datetime import date, datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple

from dotenv import load_dotenv

load_dotenv()
print(f"[DEBUG] Python en uso: {sys.version}")

# =========================
# CONFIG (por entorno)
# =========================
DAILY_JSON_DIR = os.getenv("DAILY_JSON_DIR", r"C:\Users\I7 8700\OneDrive\Documentos\proyectos\json_out")
DAILY_JSON_GLOB = os.getenv("DAILY_JSON_GLOB", "daily_market_snapshot*.json")

WEEKLY_OUT_DIR = os.getenv("WEEKLY_OUT_DIR", DAILY_JSON_DIR)

DF_SUMMARY_DIR = os.getenv("DF_SUMMARY_DIR", r"C:\Users\I7 8700\OneDrive\Documentos\df\df_data")
DF_SUMMARY_GLOB = os.getenv("DF_SUMMARY_GLOB", "resumen_df_*.txt")

# Email IMAP (mismo esquema que usas en el diario)
EMAIL_IMAP_HOST = os.getenv("EMAIL_IMAP_HOST", "imap.gmail.com")
EMAIL_IMAP_PORT = int(os.getenv("EMAIL_IMAP_PORT", "993"))
EMAIL_USERNAME = os.getenv("EMAIL_USERNAME")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_FOLDER = os.getenv("EMAIL_FOLDER", "INBOX")

# SURA weekly
SURA_SENDER = os.getenv("SURA_SENDER", "comunicaciones.cl@comunicaciones.surainvestments.com")
SURA_BODY_MARKER = os.getenv("SURA_BODY_MARKER", "HECHOS QUE MARCARON LA SEMANA")


# =========================
# HELPERS
# =========================
def safe_float(x) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def parse_yyyy_mm_dd(s: str) -> Optional[date]:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def extract_date_from_daily_json_path(path: str) -> Optional[date]:
    # Busca YYYY-MM-DD en el nombre del archivo
    m = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(path))
    if m:
        return parse_yyyy_mm_dd(m.group(1))
    return None


def load_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] No pude leer {path}: {e}")
        return None


def list_daily_snapshots_between(start_d: date, end_d: date) -> List[Tuple[date, str]]:
    paths = glob.glob(os.path.join(DAILY_JSON_DIR, DAILY_JSON_GLOB))
    out: List[Tuple[date, str]] = []
    for p in paths:
        d = extract_date_from_daily_json_path(p)
        if not d:
            j = load_json(p)
            if j and "date" in j:
                d = parse_yyyy_mm_dd(str(j["date"]))
        if d and start_d <= d <= end_d:
            out.append((d, p))
    out.sort(key=lambda x: x[0])
    return out


def pick_last_trading_week(end_d: date, days: int = 5, lookback: int = 14) -> List[Tuple[date, str]]:
    start = end_d - timedelta(days=lookback)
    candidates = list_daily_snapshots_between(start, end_d)
    if not candidates:
        return []
    # toma los últimos N snapshots disponibles (trading days)
    return candidates[-days:]


def html_to_text(html: str) -> str:
    if not html:
        return ""
    text = unescape(html)
    text = re.sub(r"(?is)<(script|style).*?>.*?(</\1>)", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_text_from_email_message(msg: email.message.Message) -> str:
    parts: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "").lower()
            if "attachment" in disp:
                continue

            payload = None
            try:
                payload = part.get_payload(decode=True)
            except Exception:
                payload = None
            if not payload:
                continue

            charset = part.get_content_charset() or "utf-8"
            try:
                decoded = payload.decode(charset, errors="replace")
            except Exception:
                decoded = payload.decode("utf-8", errors="replace")

            if ctype == "text/plain":
                parts.append(decoded)
            elif ctype == "text/html" and not parts:
                parts.append(html_to_text(decoded))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                decoded = payload.decode(charset, errors="replace")
            except Exception:
                decoded = payload.decode("utf-8", errors="replace")

            ctype = msg.get_content_type()
            if ctype == "text/plain":
                parts.append(decoded)
            elif ctype == "text/html":
                parts.append(html_to_text(decoded))

    return "\n".join(parts).strip()


def decode_subject(msg: email.message.Message) -> str:
    raw_subject = msg.get("Subject", "")
    dh = decode_header(raw_subject)
    if not dh:
        return raw_subject
    piece, enc = dh[0]
    if isinstance(piece, bytes):
        try:
            return piece.decode(enc or "utf-8", errors="replace")
        except Exception:
            return piece.decode("utf-8", errors="replace")
    return str(piece)


def fetch_latest_sura_weekly_email() -> Optional[Dict[str, Any]]:
    if not EMAIL_USERNAME or not EMAIL_PASSWORD:
        print("[SURA] EMAIL_USERNAME/EMAIL_PASSWORD no definidos. Se omite SURA.")
        return None

    try:
        mail = imaplib.IMAP4_SSL(EMAIL_IMAP_HOST, EMAIL_IMAP_PORT)
        mail.login(EMAIL_USERNAME, EMAIL_PASSWORD)
        mail.select(EMAIL_FOLDER)
    except Exception as e:
        print(f"[SURA] No pude conectar IMAP: {e}")
        return None

    try:
        status, data = mail.search(None, "FROM", SURA_SENDER)
        if status != "OK":
            print(f"[SURA] SEARCH no OK: {status}")
            mail.logout()
            return None
        msg_ids = data[0].split()
        if not msg_ids:
            print("[SURA] No hay correos desde SURA sender.")
            mail.logout()
            return None

        # Recorremos desde el más reciente hacia atrás y elegimos el primero que tenga el marcador en el BODY
        for mid in reversed(msg_ids[-50:]):  # limitamos búsqueda a los últimos 50
            st, msg_data = mail.fetch(mid, "(RFC822)")
            if st != "OK":
                continue
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            body = extract_text_from_email_message(msg)
            if SURA_BODY_MARKER.lower() in (body or "").lower():
                subject = decode_subject(msg)
                email_date = msg.get("Date", "")
                mail.logout()
                return {
                    "source": "SURA Investments (Weekly)",
                    "subject": subject,
                    "email_date": email_date,
                    "marker": SURA_BODY_MARKER,
                    "raw_text": body.strip(),
                }

        mail.logout()
        print("[SURA] Encontré correos desde sender, pero ninguno con el marcador en el cuerpo.")
        return None

    except Exception as e:
        print(f"[SURA] Error IMAP: {e}")
        try:
            mail.logout()
        except Exception:
            pass
        return None


def parse_df_summary_file_date(path: str) -> Optional[date]:
    # ejemplo: resumen_df_20251203_235906.txt  -> 2025-12-03
    m = re.search(r"resumen_df_(\d{8})_\d{6}", os.path.basename(path))
    if not m:
        return None
    ymd = m.group(1)
    try:
        return datetime.strptime(ymd, "%Y%m%d").date()
    except Exception:
        return None


def load_df_summaries_between(start_d: date, end_d: date) -> List[Dict[str, Any]]:
    paths = glob.glob(os.path.join(DF_SUMMARY_DIR, DF_SUMMARY_GLOB))
    rows: List[Dict[str, Any]] = []
    for p in paths:
        d = parse_df_summary_file_date(p)
        if not d:
            continue
        if start_d <= d <= end_d:
            try:
                txt = open(p, "r", encoding="utf-8", errors="replace").read().strip()
            except Exception:
                txt = ""
            rows.append({"file": os.path.basename(p), "date": d.isoformat(), "text": txt})
    rows.sort(key=lambda x: x["date"])
    return rows


# =========================
# AGGREGATION
# =========================
def weekly_change(first: Optional[float], last: Optional[float]) -> Optional[float]:
    if first is None or last is None or first == 0:
        return None
    return (last / first - 1.0) * 100.0


def build_weekly_block_from_daily(
    dailies: List[Dict[str, Any]],
    block_key: str,
) -> Dict[str, Any]:
    # dailies: lista ordenada por fecha ascendente
    # block_key: "equity", "rates_bonds", "fx", "commodities"
    if not dailies:
        return {"items": [], "note": "Sin datos diarios"}

    first = dailies[0].get(block_key, []) or []
    last = dailies[-1].get(block_key, []) or []

    first_map = {x.get("symbol"): x for x in first if x.get("symbol")}
    last_map = {x.get("symbol"): x for x in last if x.get("symbol")}

    out_items: List[Dict[str, Any]] = []
    for sym, last_item in last_map.items():
        first_item = first_map.get(sym, {})
        last_close = safe_float(last_item.get("close"))
        first_close = safe_float(first_item.get("close"))

        w = weekly_change(first_close, last_close)
        # mensual y YTD desde el último snapshot (ya viene calculado por tu daily)
        mtd = safe_float(last_item.get("change_mtd"))
        ytd = safe_float(last_item.get("change_ytd"))

        out_items.append({
            "symbol": sym,
            "name": last_item.get("name"),
            "close": last_close,
            "last_date": last_item.get("last_date"),
            "change_week": round(w, 2) if w is not None else None,
            "change_mtd": round(mtd, 2) if mtd is not None else None,
            "change_ytd": round(ytd, 2) if ytd is not None else None,
        })

    out_items.sort(key=lambda x: (x.get("name") or x.get("symbol") or ""))
    return {"items": out_items}


def build_weekly_chile_block(dailies: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not dailies:
        return {}

    def get_chile_value(day: Dict[str, Any], key: str) -> Optional[float]:
        ch = day.get("chile") or {}
        if key not in ch:
            return None
        if isinstance(ch[key], dict):
            return safe_float(ch[key].get("value"))
        return safe_float(ch[key])

    first = dailies[0]
    last = dailies[-1]

    # dólar observado (CLP por USD): semanal desde observado vs observado
    first_usdclp = get_chile_value(first, "dolar_obs") or get_chile_value(first, "dolar_observado")
    last_usdclp = get_chile_value(last, "dolar_obs") or get_chile_value(last, "dolar_observado")
    usdclp_week = weekly_change(first_usdclp, last_usdclp)

    peso_dir_week = None
    if usdclp_week is not None:
        if usdclp_week > 0:
            peso_dir_week = "depreciación"
        elif usdclp_week < 0:
            peso_dir_week = "apreciación"

    # mensual y YTD: buscamos primer valor del mes y del año dentro de los snapshots disponibles
    def first_in_month(key: str) -> Optional[float]:
        target_month = parse_yyyy_mm_dd(str(last.get("date", ""))) or date.today()
        month = target_month.month
        year = target_month.year
        for day in dailies:
            d = parse_yyyy_mm_dd(str(day.get("date", "")))
            if d and d.year == year and d.month == month:
                v = get_chile_value(day, key)
                if v is not None:
                    return v
        return None

    def first_in_year(key: str) -> Optional[float]:
        target_year = (parse_yyyy_mm_dd(str(last.get("date", ""))) or date.today()).year
        for day in dailies:
            d = parse_yyyy_mm_dd(str(day.get("date", "")))
            if d and d.year == target_year:
                v = get_chile_value(day, key)
                if v is not None:
                    return v
        return None

    usdclp_month_first = first_in_month("dolar_obs") or first_in_month("dolar_observado")
    usdclp_year_first = first_in_year("dolar_obs") or first_in_year("dolar_observado")
    usdclp_mtd = weekly_change(usdclp_month_first, last_usdclp)
    usdclp_ytd = weekly_change(usdclp_year_first, last_usdclp)

    # TPM: solo nivel (comentario lo hará el prompt si hubo cambios/expectativas)
    last_tpm = get_chile_value(last, "tpm")

    # UF: solo nivel, no comentar (lo manejan los prompts)
    last_uf = get_chile_value(last, "uf")

    # IPSA: viene en equity como ^IPSA, igual lo dejamos acá como acceso directo
    ipsa_close = None
    equity_last = last.get("equity") or []
    for it in equity_last:
        if it.get("symbol") == "^IPSA":
            ipsa_close = safe_float(it.get("close"))

    return {
        "tpm": {"value": last_tpm, "date": last.get("date")},
        "uf": {"value": last_uf, "date": last.get("date")},
        "ipsa": {"close": ipsa_close, "date": last.get("date")},
        "usdclp_observado": {
            "value": last_usdclp,
            "date": last.get("date"),
            "change_week": round(usdclp_week, 2) if usdclp_week is not None else None,
            "change_mtd": round(usdclp_mtd, 2) if usdclp_mtd is not None else None,
            "change_ytd": round(usdclp_ytd, 2) if usdclp_ytd is not None else None,
            "peso_direction_week": peso_dir_week,
        },
    }


# =========================
# MAIN WEEKLY
# =========================
def build_weekly_dataset(week_end: Optional[date] = None) -> Dict[str, Any]:
    if week_end is None:
        week_end = date.today()

    daily_refs = pick_last_trading_week(week_end, days=5, lookback=14)
    if not daily_refs:
        raise RuntimeError(f"No encontré snapshots diarios en {DAILY_JSON_DIR} con patrón {DAILY_JSON_GLOB}")

    dailies: List[Dict[str, Any]] = []
    for d, path in daily_refs:
        j = load_json(path)
        if not j:
            continue
        if "date" not in j:
            j["date"] = d.isoformat()
        dailies.append(j)

    dailies.sort(key=lambda x: x.get("date", ""))

    start_date = parse_yyyy_mm_dd(str(dailies[0]["date"])) or (week_end - timedelta(days=6))
    end_date = parse_yyyy_mm_dd(str(dailies[-1]["date"])) or week_end

    weekly = {
        "week_start": start_date.isoformat(),
        "week_end": end_date.isoformat(),
        "daily_files_used": [extract_date_from_daily_json_path(p) .isoformat() if extract_date_from_daily_json_path(p) else os.path.basename(p)
                             for _, p in daily_refs],
        "equity": build_weekly_block_from_daily(dailies, "equity"),
        "rates_bonds": build_weekly_block_from_daily(dailies, "rates_bonds"),
        "fx": build_weekly_block_from_daily(dailies, "fx"),
        "commodities": build_weekly_block_from_daily(dailies, "commodities"),
        "chile": build_weekly_chile_block(dailies),
        "inputs": {
            "df_summaries": load_df_summaries_between(start_date, end_date),
            "sura_weekly_email": fetch_latest_sura_weekly_email(),
        },
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    return weekly


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--week_end", type=str, default=None, help="YYYY-MM-DD (opcional). Si no, usa hoy y toma últimos 5 snapshots.")
    ap.add_argument("--out", type=str, default=None, help="Ruta output JSON (opcional).")
    args = ap.parse_args()

    week_end = parse_yyyy_mm_dd(args.week_end) if args.week_end else None
    dataset = build_weekly_dataset(week_end)

    out_path = args.out
    if not out_path:
        out_name = f"weekly_market_snapshot_{dataset['week_end']}.json"
        out_path = os.path.join(WEEKLY_OUT_DIR, out_name)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)

    print(f"[OK] Weekly dataset guardado en: {out_path}")


if __name__ == "__main__":
    main()
