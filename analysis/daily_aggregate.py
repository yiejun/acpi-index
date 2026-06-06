"""
Daily aggregation: raw → processed
- Cleans data, deduplicates, computes per-layer averages
- Stores one row per (date, layer, metric)
"""
import pandas as pd
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

    if gpu.empty or api.empty or power.empty:
        print("⚠️ Not all layers have data yet")
        return None

    latest_date = max(gpu["date"].max(), api["date"].max(), power["date"].max())

    gpu_avg = gpu[gpu["date"] == gpu["date"].max()]["price_per_gpu_hour_usd"].mean()
    api_input_avg = api[api["date"] == api["date"].max()]["avg_input"].mean()
    api_output_avg = api[api["date"] == api["date"].max()]["avg_output"].mean()
    api_composite = (api_input_avg * 2 + api_output_avg) / 3  # 2:1 input:output ratio
    power_avg = power[power["date"] == power["date"].max()]["price_cents_kwh"].mean()

    return {
        "date": str(latest_date),
        "layer1_gpu_avg_per_gpu_hr_usd": round(gpu_avg, 4),
        "layer2_api_input_avg_per_m_usd": round(api_input_avg, 4),
        "layer2_api_output_avg_per_m_usd": round(api_output_avg, 4),
        "layer2_api_composite_per_m_usd": round(api_composite, 4),
        "layer3_power_avg_cents_kwh": round(power_avg, 4),
    }


def main():
    PROCESSED.mkdir(parents=True, exist_ok=True)

    # Save per-layer aggregates
    for name, df in [("gpu", aggregate_gpu()),
                     ("api", aggregate_api()),
                     ("power", aggregate_power())]:
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
                subset=["date"], keep="last"
            )
        snap_df.to_parquet(out, index=False)
        print(f"\n=== ACPI Snapshot ({snap['date']}) ===")
        for k, v in snap.items():
            if k != "date":
                print(f"  {k}: {v}")


if __name__ == "__main__":
    main()