"""
PCA-derived weights for each layer.
Falls back to equal weights when insufficient data (< 7 timestamps).
"""
import pandas as pd
import numpy as np
from sklearn.decomposition import PCA
from pathlib import Path

RAW = Path("data/raw")
MIN_OBS = 7


def _pca_weights(pivot):
    if pivot.shape[0] < MIN_OBS or pivot.shape[1] < 2:
        n = pivot.shape[1] if pivot.shape[1] else 1
        return {c: 1/n for c in pivot.columns}, "equal"

    # Drop columns with zero variance (would cause inf in standardization)
    std = pivot.std(ddof=0)
    valid_cols = std[std > 0].index.tolist()
    if len(valid_cols) < 2:
        n = pivot.shape[1]
        return {c: 1/n for c in pivot.columns}, "equal_zero_variance"

    pivot_v = pivot[valid_cols]
    X = (pivot_v - pivot_v.mean()) / pivot_v.std(ddof=0)
    X = X.replace([np.inf, -np.inf], np.nan).dropna(axis=1, how="any")
    if X.shape[1] < 2:
        n = pivot.shape[1]
        return {c: 1/n for c in pivot.columns}, "equal_too_sparse"

    pca = PCA(n_components=1)
    pca.fit(X.values)
    loadings = pca.components_[0]
    if loadings.sum() < 0:
        loadings = -loadings
    abs_load = np.abs(loadings)
    if abs_load.sum() == 0:
        n = X.shape[1]
        return {c: 1/n for c in X.columns}, "equal"
    weights = abs_load / abs_load.sum()
    # Pad: any column dropped gets 0 weight
    full = {c: 0.0 for c in pivot.columns}
    full.update(dict(zip(X.columns, weights)))
    return full, "pca"


def _load(folder):
    files = sorted((RAW / folder).glob("*.parquet"))
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def gpu_weights():
    dfs = []
    for folder in ["aws_gpu", "lambda_gpu", "coreweave_gpu", "azure_gpu"]:
        df = _load(folder)
        if df.empty: continue
        # Apply same noise filters as daily_aggregate
        if folder == "lambda_gpu":
            df = df[df["price_per_gpu_hour_usd"] < 6]
        if folder == "coreweave_gpu":
            df = df[df["gpu_type"] != "H100-Unknown"]
        if folder == "azure_gpu":
            df = df[df["region"].str.startswith(("eastus", "westus"))]
        df["provider"] = folder.replace("_gpu", "")
        df["ts"] = pd.to_datetime(df["timestamp"])
        agg = df.groupby(["ts", "provider"])["price_per_gpu_hour_usd"].mean().reset_index()
        dfs.append(agg)
    if not dfs:
        return {}, "no_data"
    combined = pd.concat(dfs, ignore_index=True)
    pivot = combined.pivot_table(index="ts", columns="provider",
                                  values="price_per_gpu_hour_usd").sort_index().ffill().dropna()
    return _pca_weights(pivot)


def api_weights():
    df = _load("api_pricing")
    if df.empty: return {}, "no_data"
    df = df[df["tier"] == "workhorse"]
    df["ts"] = pd.to_datetime(df["timestamp"])
    df["composite"] = (df["input_price_per_million_usd"] * 2 +
                       df["output_price_per_million_usd"]) / 3
    agg = df.groupby(["ts", "provider"])["composite"].mean().reset_index()
    pivot = agg.pivot_table(index="ts", columns="provider",
                             values="composite").sort_index().ffill().dropna()
    return _pca_weights(pivot)


def power_weights():
    df = _load("power_price")
    if df.empty: return {}, "no_data"
    df["ts"] = pd.to_datetime(df["timestamp"])
    agg = df.groupby(["ts", "state"])["price_cents_per_kwh"].mean().reset_index()
    pivot = agg.pivot_table(index="ts", columns="state",
                             values="price_cents_per_kwh").sort_index().ffill().dropna()
    return _pca_weights(pivot)


def market_weights():
    df = _load("market_signal")
    if df.empty: return {}, "no_data"
    df["ts"] = pd.to_datetime(df["timestamp"])
    agg = df.groupby(["ts", "ticker"])["close_usd"].mean().reset_index()
    pivot = agg.pivot_table(index="ts", columns="ticker",
                             values="close_usd").sort_index().ffill().dropna()
    return _pca_weights(pivot)


def all_weights():
    return {"gpu": gpu_weights(), "api": api_weights(),
            "power": power_weights(), "market": market_weights()}


if __name__ == "__main__":
    for layer, (w, mode) in all_weights().items():
        print(f"\n[{layer}] mode={mode}")
        for k, v in w.items():
            print(f"  {k}: {v:.4f}")