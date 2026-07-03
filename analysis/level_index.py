"""
ACPI Level Index — chained Tornqvist price index (base = 100).

ln(I_t / I_{t-1}) = sum_i w_i * ln(P_{i,t} / P_{i,t-1})

Level index = f(x). The z-score composite = f'(x) (momentum).
Daily frequency: last snapshot per date.
"""
import numpy as np
import pandas as pd
from pathlib import Path

PROCESSED = Path("data/processed")
SNAP_FILE = PROCESSED / "acpi_snapshots.parquet"
OUT_FILE = PROCESSED / "acpi_level.parquet"

WEIGHTS = {"gpu": 0.50, "api": 0.27, "power": 0.13, "market": 0.10}
BASE = 100.0

LAYER_COLS = {
    "gpu": "layer1_gpu_avg_per_gpu_hr_usd",
    "api": "layer2_api_composite_per_m_usd",
    "power": "layer3_power_avg_cents_kwh",
    "market": "layer4_market_avg_close_usd",
}


def main():
    if not SNAP_FILE.exists():
        print(f"No snapshots found at {SNAP_FILE}")
        return

    df = pd.read_parquet(SNAP_FILE).sort_values("timestamp")

    # One row per day (last observation of the day)
    daily = df.groupby("date").last().reset_index()
    daily = daily.sort_values("date").reset_index(drop=True)

    prices = daily[[LAYER_COLS[k] for k in WEIGHTS]].copy()
    prices.columns = list(WEIGHTS.keys())

    # Guard: prices must be positive for log; ffill any gaps
    prices = prices.replace(0, np.nan).ffill()

    # Chained Tornqvist: weighted sum of log price relatives, cumulated
    log_rel = np.log(prices / prices.shift(1))
    w = pd.Series(WEIGHTS)
    weighted_log_rel = log_rel.mul(w, axis=1).sum(axis=1, min_count=1)

    level = BASE * np.exp(weighted_log_rel.fillna(0).cumsum())

    out = pd.DataFrame({
        "date": daily["date"],
        "acpi_level": level.round(4),
        "chg_1d_pct": (level.pct_change(1) * 100).round(4),
        "chg_7d_pct": (level.pct_change(7) * 100).round(4),
    })
    # Per-layer contribution to today's move (pct points)
    for k in WEIGHTS:
        out[f"contrib_{k}_pct"] = (WEIGHTS[k] * log_rel[k] * 100).round(4)

    out.to_parquet(OUT_FILE, index=False)
    print(f"✓ Saved to {OUT_FILE}\n")
    print(out.tail(10).to_string(index=False))


if __name__ == "__main__":
    main()