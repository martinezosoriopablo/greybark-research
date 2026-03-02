import os
import pandas as pd
import matplotlib.pyplot as plt

MONTHLY_PATH = "data/processed/macro_chile_inflation/inflation_chile_master_monthly.parquet"
DAILY_PATH   = "data/processed/macro_chile_inflation/inflation_chile_master_daily.parquet"

OUT_DIR = "reports/monthly/charts/inflation_chile"
os.makedirs(OUT_DIR, exist_ok=True)

m = pd.read_parquet(MONTHLY_PATH).sort_index()
d = pd.read_parquet(DAILY_PATH).sort_index()

def savefig(name):
    path = os.path.join(OUT_DIR, name)
    plt.tight_layout()
    plt.savefig(path, dpi=200, bbox_inches="tight")
    plt.close()
    return path
plt.figure(figsize=(10,4))
plt.plot(m.index, m["IPC_HEADLINE_YOY"], label="IPC Total (YoY)")
plt.plot(m.index, m["IPC_SAE_YOY"], label="IPC SAE (YoY)")
plt.axhline(3, color="black", linestyle=":", alpha=0.6)
plt.title("Inflación: IPC Total vs Subyacente (SAE) — Variación 12 meses")
plt.ylabel("% a/a")
plt.grid(alpha=0.3)
plt.legend()
savefig("01_headline_vs_core_yoy.png")
plt.figure(figsize=(10,4))
plt.plot(m.index, m["IPC_HEADLINE_ANN_3M"], label="IPC Total (3m anualizado)")
plt.plot(m.index, m["IPC_SAE_ANN_3M"], label="IPC SAE (3m anualizado)")
plt.axhline(3, color="black", linestyle=":", alpha=0.6)
plt.title("Inflación: Momentum de corto plazo (3m anualizado)")
plt.ylabel("% anualizado")
plt.grid(alpha=0.3)
plt.legend()
savefig("02_momentum_3m_annualized.png")
plt.figure(figsize=(10,4))
plt.plot(m.index, m["IPC_HEADLINE_ANN_3M"], label="IPC Total (3m anualizado)")
plt.plot(m.index, m["IPC_SAE_ANN_3M"], label="IPC SAE (3m anualizado)")
plt.axhline(3, color="black", linestyle=":", alpha=0.6)
plt.title("Inflación: Momentum de corto plazo (3m anualizado)")
plt.ylabel("% anualizado")
plt.grid(alpha=0.3)
plt.legend()
savefig("02_momentum_3m_annualized.png")
plt.figure(figsize=(10,4))
plt.plot(m.index, m["IPC_HEADLINE_ANN_6M"], label="IPC Total (6m anualizado)")
plt.plot(m.index, m["IPC_SAE_ANN_6M"], label="IPC SAE (6m anualizado)")
plt.axhline(3, color="black", linestyle=":", alpha=0.6)
plt.title("Inflación: Momentum (6m anualizado)")
plt.ylabel("% anualizado")
plt.grid(alpha=0.3)
plt.legend()
savefig("02b_momentum_6m_annualized.png")
end = d.index.max()
start = end - pd.Timedelta(days=180)

dd = d.loc[start:end].copy()

fig, ax = plt.subplots(figsize=(10,4))
ax.plot(dd.index, dd["USDCLP_D"], label="USDCLP")
ax.set_title("Driver externo: Tipo de cambio (últimos 6 meses)")
ax.grid(alpha=0.3)
ax.legend()
savefig("06_usdclp_6m.png")

fig, ax = plt.subplots(figsize=(10,4))
ax.plot(dd.index, dd["WTI_D"], label="WTI")
ax.set_title("Driver externo: Petróleo WTI (últimos 6 meses)")
ax.grid(alpha=0.3)
ax.legend()
savefig("06b_wti_6m.png")
cols = [c for c in d.columns if c in ["EEE_INF_1Y_D", "EEE_INF_2Y_D", "EEE_INF_3Y_D"]]
if cols:
    end = d.index.max()
    start = end - pd.Timedelta(days=365)

    plt.figure(figsize=(10,4))
    for c in cols:
        plt.plot(d.loc[start:end].index, d.loc[start:end, c], label=c.replace("_D",""))
    plt.axhline(3, color="black", linestyle=":", alpha=0.6)
    plt.title("Expectativas de inflación (EEE) — stepwise diario (últimos 12m)")
    plt.ylabel("%")
    plt.grid(alpha=0.3)
    plt.legend()
    savefig("07_eee_inflation_12m.png")
