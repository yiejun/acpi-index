"""
Rolling 3x3 correlation matrix between layer z-scores.
Alerts when any off-diagonal pair drops below 0.3 (divergence signal).
"""
import pandas as pd
import numpy as np
from pathlib import Path

PROCESSED = Path("data/processed")
ZSCORE_FILE = PROCESSED / "acpi_zscores.parquet"

LAYERS = ["gpu_z", "api_z", "power_z", "market_z"]
DIVERGENCE_THRESHOLD = 0.3
ROLL_WINDOW = 30
MIN_OBS = 7


def main():
    if not ZSCORE_FILE.exists():
        print(f"No z-scores found at {ZSCORE_FILE}")
        return

    df = pd.read_parquet(ZSCORE_FILE).sort_values("date").reset_index(drop=True)
    print(f"Loaded {len(df)} z-score rows\n")

    rows = []
    for i in range(len(df)):
        n = i + 1
        if n < MIN_OBS:
            rows.append({"date": df.loc[i, "date"], "n_obs": n,
                         "corr_gpu_api": np.nan, "corr_gpu_power": np.nan,
                         "corr_gpu_market": np.nan, "corr_api_power": np.nan,
                         "corr_api_market": np.nan, "corr_power_market": np.nan,
                         "divergence_alert": False})
            continue

        window = df.iloc[max(0, i - ROLL_WINDOW + 1) : i + 1][LAYERS].dropna()
        if len(window) < MIN_OBS:
            rows.append({"date": df.loc[i, "date"], "n_obs": n,
                         "corr_gpu_api": np.nan, "corr_gpu_power": np.nan,
                         "corr_gpu_market": np.nan, "corr_api_power": np.nan,
                         "corr_api_market": np.nan, "corr_power_market": np.nan,
                         "divergence_alert": False})
            continue

        corr = window.corr()
        pairs = {
            "corr_gpu_api": corr.loc["gpu_z", "api_z"],
            "corr_gpu_power": corr.loc["gpu_z", "power_z"],
            "corr_gpu_market": corr.loc["gpu_z", "market_z"],
            "corr_api_power": corr.loc["api_z", "power_z"],
            "corr_api_market": corr.loc["api_z", "market_z"],
            "corr_power_market": corr.loc["power_z", "market_z"],
        }
        alert = any(abs(v) < DIVERGENCE_THRESHOLD for v in pairs.values())

        rows.append({
            "date": df.loc[i, "date"],
            "n_obs": n,
            **{k: round(v, 4) for k, v in pairs.items()},
            "divergence_alert": alert,
        })

    out_df = pd.DataFrame(rows)
    out = PROCESSED / "acpi_correlations.parquet"
    out_df.to_parquet(out, index=False)
    print(f"✓ Saved to {out}\n")
    print(out_df.to_string(index=False))


if __name__ == "__main__":
    main()