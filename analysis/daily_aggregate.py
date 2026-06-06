"""
Daily aggregation: raw → processed
- Cleans data, deduplicates, computes per-layer averages
- Stores one row per (date, layer, metric)
"""
import pandas as pd
from analysis.pca_weights import all_weights
from datetime import datetime, timezone
from pathlib import Path

RAW = Path("data/raw")
PROCESSED = Path("data/processed")


def load_all(provider_dir):
    """Load and concat all parquet files in a provider folder."""
    files = sorted((RAW / provider_dir).glob("*.parquet"))
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def aggregate_gpu():
    """Layer 1: avg H100 per-GPU per-hour across providers (US regions only)."""
    rows = []
    for provider in ["aws_gpu", "lambda_gpu", "coreweave_gpu", "azure_gpu"]:
        df = load_all(provider)
        if df.empty:
            continue
        # Take latest snapshot per timestamp
        df["date"] = pd.to_datetime(df["timestamp"]).dt.date

        # Filter noise from early test runs
        if provider == "lambda_gpu":
            df = df[df["price_per_gpu_hour_usd"] < 6]  # filter B200 contamination
        if provider == "coreweave_gpu":
            df = df[df["gpu_type"] != "H100-Unknown"]
        if provider == "azure_gpu":
            # Take only US regions for fair comparison
            df = df[df["region"].str.startswith("eastus") | df["region"].str.startswith("westus")]

        # Daily avg per provider
        daily = df.groupby("date")["price_per_gpu_hour_usd"].mean().reset_index()
        daily["provider"] = provider.replace("_gpu", "")
        rows.append(daily)

    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def aggregate_api():
    """Layer 2: avg input/output prices across providers."""
    df = load_all("api_pricing")
    if df.empty:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["timestamp"]).dt.date
    # Workhorse tier only for fair comparison (flagship pricing varies more)
    df = df[df["tier"] == "workhorse"]
    daily = df.groupby(["date", "provider"]).agg(
        avg_input=("input_price_per_million_usd", "mean"),
        avg_output=("output_price_per_million_usd", "mean"),
    ).reset_index()
    return daily

def aggregate_market():
    """Layer 4: NVDA + AI ETFs daily prices."""
    df = load_all("market_signal")
    if df.empty:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["timestamp"]).dt.date
    # Daily avg per ticker (in case of multiple snapshots per day)
    daily = df.groupby(["date", "ticker"]).agg(
        close_usd=("close_usd", "mean"),
        pct_change_1d=("pct_change_1d", "mean"),
    ).reset_index()
    return daily

def aggregate_power():
    """Layer 3: avg industrial electricity price across DC states."""
    df = load_all("power_price")
    if df.empty:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["timestamp"]).dt.date
    # Latest month only (EIA is monthly data)
    latest_period = df["period"].max()
    df = df[df["period"] == latest_period]
    daily = df.groupby(["date", "state"]).agg(
        price_cents_kwh=("price_cents_per_kwh", "mean"),
    ).reset_index()
    return daily


def compute_acpi_snapshot():
    """Compute today's ACPI snapshot — single composite number per layer."""
    gpu = aggregate_gpu()
    api = aggregate_api()
    power = aggregate_power()
    market = aggregate_market()

    if gpu.empty or api.empty or power.empty or market.empty:
        print("⚠️ Not all layers have data yet")
        return None

    latest_date = max(gpu["date"].max(), api["date"].max(), power["date"].max())

    weights = all_weights()

    def weighted(df, key_col, value_col, weights_dict):
        latest = df[df["date"] == df["date"].max()]
        if not weights_dict:
            return latest[value_col].mean()
        total, wsum = 0.0, 0.0
        for key, w in weights_dict.items():
            vals = latest[latest[key_col] == key][value_col]
            if not vals.empty and w > 0:
                total += w * vals.mean()
                wsum += w
        return total / wsum if wsum > 0 else latest[value_col].mean()

    gpu_w, gpu_mode = weights["gpu"]
    api_w, api_mode = weights["api"]
    power_w, power_mode = weights["power"]
    market_w, market_mode = weights["market"]

    gpu_avg = weighted(gpu, "provider", "price_per_gpu_hour_usd", gpu_w)
    api_input_avg = weighted(api, "provider", "avg_input", api_w)
    api_output_avg = weighted(api, "provider", "avg_output", api_w)
    api_composite = (api_input_avg * 2 + api_output_avg) / 3
    power_avg = weighted(power, "state", "price_cents_kwh", power_w)
    market_avg = weighted(market, "ticker", "close_usd", market_w)
    timestamp_str = datetime.now(timezone.utc).isoformat()

    return {
        "timestamp": timestamp_str,
        "date": str(latest_date),
        "layer1_gpu_avg_per_gpu_hr_usd": round(gpu_avg, 4),
        "layer2_api_input_avg_per_m_usd": round(api_input_avg, 4),
        "layer2_api_output_avg_per_m_usd": round(api_output_avg, 4),
        "layer2_api_composite_per_m_usd": round(api_composite, 4),
        "layer3_power_avg_cents_kwh": round(power_avg, 4),
        "layer4_market_avg_close_usd": round(market_avg, 4),

    }


def main():
    PROCESSED.mkdir(parents=True, exist_ok=True)

    # Save per-layer aggregates
    for name, df in [("gpu", aggregate_gpu()),
                     ("api", aggregate_api()),
                     ("power", aggregate_power()),
                     ("market", aggregate_market())]:
        if df.empty:
            continue
        out = PROCESSED / f"{name}_daily.parquet"
        df.to_parquet(out, index=False)
        print(f"✓ {name}: {len(df)} rows → {out}")

    # ACPI snapshot
    snap = compute_acpi_snapshot()
    if snap:
        snap_df = pd.DataFrame([snap])
        out = PROCESSED / "acpi_snapshots.parquet"
        if out.exists():
            existing = pd.read_parquet(out)
        snap_df = pd.concat([existing, snap_df], ignore_index=True).drop_duplicates(
            subset=["timestamp"], keep="last"
        )        
        
        snap_df.to_parquet(out, index=False)
        print(f"\n=== ACPI Snapshot ({snap['date']}) ===")
        for k, v in snap.items():
            if k != "date":
                print(f"  {k}: {v}")


if __name__ == "__main__":
    main()