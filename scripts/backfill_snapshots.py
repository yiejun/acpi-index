import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from pathlib import Path
from analysis.pca_weights import all_weights

RAW = Path("data/raw")
OUT = Path("data/processed/acpi_snapshots.parquet")
WINDOW = pd.Timedelta(minutes=15)

def read(folder):
    files = list((RAW / folder).glob("*.parquet"))
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True) if files else pd.DataFrame()

sources = {n: read(f) for n, f in [("aws","aws_gpu"),("lambda","lambda_gpu"),("coreweave","coreweave_gpu"),("azure","azure_gpu"),("api","api_pricing"),("power","power_price"),("market","market_signal")]}

for k, df in sources.items():
    if not df.empty: df["ts_dt"] = pd.to_datetime(df["timestamp"])

def near(df, ts):
    if df.empty: return pd.DataFrame()
    return df[(df["ts_dt"] - ts).abs() <= WINDOW]

def filt_gpu(df, src):
    if src == "lambda": df = df[df["price_per_gpu_hour_usd"] < 6]
    elif src == "coreweave": df = df[df["gpu_type"] != "H100-Unknown"]
    elif src == "azure": df = df[df["region"].str.startswith(("eastus","westus"))]
    return df

def w_avg(vals_dict, weights):
    if not weights:
        all_v = [v for vs in vals_dict.values() for v in vs]
        return sum(all_v)/len(all_v) if all_v else None
    total, ws = 0.0, 0.0
    for k, w in weights.items():
        vs = vals_dict.get(k, [])
        if vs and w > 0:
            total += w * (sum(vs)/len(vs)); ws += w
    return total/ws if ws > 0 else None

weights = all_weights()
gpu_w = weights["gpu"][0]; api_w = weights["api"][0]
power_w = weights["power"][0]; market_w = weights["market"][0]

anchors = sorted(sources["aws"]["timestamp"].unique())
snaps = []
for ts in anchors:
    ts_dt = pd.to_datetime(ts)
    gpu_d = {}
    for src in ["aws","lambda","coreweave","azure"]:
        df = near(sources[src], ts_dt)
        df = filt_gpu(df, src)
        if not df.empty: gpu_d[src] = df["price_per_gpu_hour_usd"].tolist()
    api_df = near(sources["api"], ts_dt)
    api_df = api_df[api_df["tier"] == "workhorse"] if not api_df.empty else api_df
    api_in = {p: api_df[api_df["provider"]==p]["input_price_per_million_usd"].tolist() for p in api_df["provider"].unique()} if not api_df.empty else {}
    api_out = {p: api_df[api_df["provider"]==p]["output_price_per_million_usd"].tolist() for p in api_df["provider"].unique()} if not api_df.empty else {}
    p_df = near(sources["power"], ts_dt)
    p_d = {s: p_df[p_df["state"]==s]["price_cents_per_kwh"].tolist() for s in p_df["state"].unique()} if not p_df.empty else {}
    m_df = near(sources["market"], ts_dt)
    m_d = {t: m_df[m_df["ticker"]==t]["close_usd"].tolist() for t in m_df["ticker"].unique()} if not m_df.empty else {}
    if not (gpu_d and api_in and p_d and m_d): continue
    gpu_a = w_avg(gpu_d, gpu_w)
    api_in_a = w_avg(api_in, api_w); api_out_a = w_avg(api_out, api_w)
    snaps.append({
        "timestamp": ts, "date": ts_dt.date(),
        "layer1_gpu_avg_per_gpu_hr_usd": round(gpu_a, 4),
        "layer2_api_input_avg_per_m_usd": round(api_in_a, 4),
        "layer2_api_output_avg_per_m_usd": round(api_out_a, 4),
        "layer2_api_composite_per_m_usd": round((api_in_a*2 + api_out_a)/3, 4),
        "layer3_power_avg_cents_kwh": round(w_avg(p_d, power_w), 4),
        "layer4_market_avg_close_usd": round(w_avg(m_d, market_w), 4),
    })

df = pd.DataFrame(snaps).sort_values("timestamp").reset_index(drop=True)
df.to_parquet(OUT, index=False)
print(f"✓ Rebuilt {len(df)} snapshots from raw")
print(df[["timestamp","layer1_gpu_avg_per_gpu_hr_usd","layer4_market_avg_close_usd"]])