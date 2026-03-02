import os
import yaml
import requests
import pandas as pd
import numpy as np
from datetime import date

BCCH_URL = "https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx"

BCCH_USER = "martinezosoriopablo@gmail.com"
BCCH_PASS = "PabMar2604$"
if BCCH_USER == "TU_USER" or BCCH_PASS == "TU_PASS":
    raise ValueError("Setea BCCH_USER y BCCH_PASS en variables de entorno.")

def get_series_bcch(code: str, start="2008-01-01", end=None) -> pd.Series:
    if end is None:
        end = pd.Timestamp.today().strftime("%Y-%m-%d")
    params = {
        "user": BCCH_USER,
        "pass": BCCH_PASS,
        "function": "GetSeries",
        "timeseries": code,
        "firstdate": start,
        "lastdate": end,
    }
    r = requests.get(BCCH_URL, params=params, timeout=30)
    r.raise_for_status()
    obs = r.json()["Series"]["Obs"]
    df = pd.DataFrame(obs)
    df["date"] = pd.to_datetime(df["indexDateString"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    s = df.set_index("date")["value"].sort_index()
    return s

def load_registry(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def infer_freq(series_meta):
    # usamos meta['freq'] como truth
    return series_meta["freq"]

def to_daily_stepwise(monthly_series: pd.Series) -> pd.Series:
    # convierte mensual a diario con step function (ffill sobre daily index)
    if monthly_series.empty:
        return monthly_series
    daily_index = pd.date_range(monthly_series.index.min(), pd.Timestamp.today(), freq="D")
    return monthly_series.reindex(daily_index).ffill()

def annualize_from_mom(mom_pct: pd.Series, months: int) -> pd.Series:
    # mom_pct en % (ej 0.3). Convierte a tasa anualizada basada en promedio geométrico de n meses.
    # (1 + m/100)^(12/n) - 1
    x = 1.0 + (mom_pct / 100.0)
    roll = x.rolling(months).apply(np.prod, raw=True)  # producto geométrico
    ann = (roll ** (12.0 / months) - 1.0) * 100.0
    return ann

def yoy_from_index(index: pd.Series) -> pd.Series:
    return (index / index.shift(12) - 1.0) * 100.0

# ------------------------
# MAIN
# ------------------------
REG_PATH = "inflation_chile_registry.yaml"  # ajusta ruta
START = "2008-01-01"

reg = load_registry(REG_PATH)
series_list = reg["series"]

# Descarga en dict
data = {}
for s in series_list:
    name, code = s["name"], s["code"]
    print(f"Downloading {name} ({code})...")
    data[name] = get_series_bcch(code, start=START)

# Separamos por frecuencia declarada
daily_cols = [s["name"] for s in series_list if s["freq"] == "D"]
monthly_cols = [s["name"] for s in series_list if s["freq"] == "M"]

df_d = pd.concat({k: data[k] for k in daily_cols}, axis=1).sort_index() if daily_cols else pd.DataFrame()
df_m = pd.concat({k: data[k] for k in monthly_cols}, axis=1).sort_index() if monthly_cols else pd.DataFrame()

# Stepwise diarios para expectativas (EEE)
for s in series_list:
    if "stepwise_daily_ffill" in s.get("transforms", []):
        name = s["name"]
        df_d[name + "_D"] = to_daily_stepwise(data[name])

# ------------------------
# FEATURES (Mensuales)
# ------------------------
feat = pd.DataFrame(index=df_m.index)

# IPC YoY desde índices (si existen)
if "IPC_HEADLINE_INDEX" in df_m.columns:
    feat["IPC_HEADLINE_YOY"] = yoy_from_index(df_m["IPC_HEADLINE_INDEX"])

if "IPC_SAE_INDEX" in df_m.columns:
    feat["IPC_SAE_YOY"] = yoy_from_index(df_m["IPC_SAE_INDEX"])

# Momentum anualizado desde MoM
for col in ["IPC_HEADLINE_MOM", "IPC_SAE_MOM", "IPC_SERVICES_MOM", "IPC_GOODS_MOM",
            "IPC_TRADABLES_MOM", "IPC_NONTRADABLES_MOM"]:
    if col in df_m.columns:
        feat[col.replace("_MOM", "_ANN_3M")] = annualize_from_mom(df_m[col], 3)
        feat[col.replace("_MOM", "_ANN_6M")] = annualize_from_mom(df_m[col], 6)

# Spreads estructurales (persistencia)
if "IPC_SERVICES_MOM" in df_m.columns and "IPC_GOODS_MOM" in df_m.columns:
    feat["SERVICES_MINUS_GOODS_MOM"] = df_m["IPC_SERVICES_MOM"] - df_m["IPC_GOODS_MOM"]

if "IPC_NONTRADABLES_MOM" in df_m.columns and "IPC_TRADABLES_MOM" in df_m.columns:
    feat["NONTRAD_MINUS_TRAD_MOM"] = df_m["IPC_NONTRADABLES_MOM"] - df_m["IPC_TRADABLES_MOM"]

# IPP YoY (si usas índice)
if "IPP_INDUSTRY_INDEX" in df_m.columns:
    feat["IPP_INDUSTRY_YOY"] = yoy_from_index(df_m["IPP_INDUSTRY_INDEX"])

# ------------------------
# MERGE MASTER
# ------------------------
inflation_chile_master_m = pd.concat([df_m, feat], axis=1).sort_index()
inflation_chile_master_d = df_d.sort_index()

# ------------------------
# SAVE (pipeline mensual)
# ------------------------
out_dir = "data/processed/macro_chile_inflation"
os.makedirs(out_dir, exist_ok=True)

inflation_chile_master_m.to_parquet(f"{out_dir}/inflation_chile_master_monthly.parquet")
inflation_chile_master_d.to_parquet(f"{out_dir}/inflation_chile_master_daily.parquet")

inflation_chile_master_m.to_csv(f"{out_dir}/inflation_chile_master_monthly.csv")
inflation_chile_master_d.to_csv(f"{out_dir}/inflation_chile_master_daily.csv")

print("DONE ✅")
print("Monthly shape:", inflation_chile_master_m.shape)
print("Daily shape:", inflation_chile_master_d.shape)
