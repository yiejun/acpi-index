"""
Adaptive Z-score + ACPI weighted score computation.
Window logic:
  - <7 obs: NaN (not enough data)
  - 7-29 obs: expanding window
  - 30+ obs: rolling 30-day window
"""
import numpy as np
import pandas as pd
from pathlib import Path

PROCESSED = Path("data/processed")
SNAP_FILE = PROCESSED / "acpi_snapshots.parquet"

WEIGHTS = {"gpu": 0.50, "api": 0.27, "power": 0.13, "market": 0.10}
ROLL_WINDOW = 30
MIN_OBS = 7

LAYER_COLS = {
    "gpu": "layer1_gpu_avg_per_gpu_hr_usd",
    "api": "layer2_api_composite_per_m_usd",
    "power": "layer3_power_avg_cents_kwh",
    "market": "layer4_market_avg_close_usd",
}



def adaptive_zscore(series):
    """Compute z-score using adaptive window."""
    z = pd.Series(index=series.index, dtype=float)
    for i in range(len(series)):
        n = i + 1
        if n < MIN_OBS:
            z.iloc[i] = np.nan
        elif n < ROLL_WINDOW:
            # Expanding window
            window = series.iloc[:n]
            std = window.std()
            z.iloc[i] = (series.iloc[i] - window.mean()) / std if std > 0 else 0
        else:
            # Rolling 30-period window
            window = series.iloc[i - ROLL_WINDOW + 1 : i + 1]
            std = window.std()
            z.iloc[i] = (series.iloc[i] - window.mean()) / std if std > 0 else 0
    return z


def main():
    if not SNAP_FILE.exists():
        print(f"No snapshots found at {SNAP_FILE}")
        return

    df = pd.read_parquet(SNAP_FILE).sort_values("timestamp").reset_index(drop=True)
    print(f"Loaded {len(df)} snapshots\n")

    # Compute z-scores per layer
    for layer, col in LAYER_COLS.items():
        df[f"{layer}_z"] = adaptive_zscore(df[col])

    # ACPI composite score (weighted sum of z-scores)
    df["acpi_score"] = (
        WEIGHTS["gpu"] * df["gpu_z"]
        + WEIGHTS["api"] * df["api_z"]
        + WEIGHTS["power"] * df["power_z"]
        + WEIGHTS["market"] * df["market_z"]
    )

    df["n_obs"] = range(1, len(df) + 1)
    df["window_mode"] = df["n_obs"].apply(
        lambda n: "insufficient" if n < MIN_OBS
        else "expanding" if n < ROLL_WINDOW
        else "rolling_30"
    )

    # Save
    out = PROCESSED / "acpi_zscores.parquet"
    df.to_parquet(out, index=False)
    print(f"✓ Saved to {out}\n")

    # Display
    cols = ["date", "n_obs", "window_mode", "gpu_z", "api_z", "power_z", "market_z", "acpi_score"]
    print(df[cols].to_string(index=False))


if __name__ == "__main__":
    main()