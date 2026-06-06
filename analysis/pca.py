"""
PCA master signal — extract PC1 from 3 layer z-scores.
PC1 = single 'AI compute temperature' number.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.decomposition import PCA

PROCESSED = Path("data/processed")
ZSCORE_FILE = PROCESSED / "acpi_zscores.parquet"

LAYERS = ["gpu_z", "api_z", "power_z"]
MIN_OBS = 7


def main():
    if not ZSCORE_FILE.exists():
        print(f"No z-scores found at {ZSCORE_FILE}")
        return

    df = pd.read_parquet(ZSCORE_FILE).sort_values("date").reset_index(drop=True)

    # Need at least MIN_OBS complete rows
    valid = df.dropna(subset=LAYERS)
    if len(valid) < MIN_OBS:
        print(f"⚠️  Only {len(valid)} valid rows, need {MIN_OBS}. PCA skipped.")
        df["pc1"] = np.nan
        df["pc1_variance_explained"] = np.nan
        df.to_parquet(PROCESSED / "acpi_pca.parquet", index=False)
        return

    X = valid[LAYERS].values
    pca = PCA(n_components=3)
    pcs = pca.fit_transform(X)

    pc1_series = pd.Series(np.nan, index=df.index)
    pc1_series.loc[valid.index] = pcs[:, 0]

    df["pc1"] = pc1_series
    df["pc1_variance_explained"] = pca.explained_variance_ratio_[0]
    df["loading_gpu"] = pca.components_[0, 0]
    df["loading_api"] = pca.components_[0, 1]
    df["loading_power"] = pca.components_[0, 2]

    out = PROCESSED / "acpi_pca.parquet"
    df.to_parquet(out, index=False)
    print(f"✓ Saved to {out}\n")
    print(f"PC1 variance explained: {pca.explained_variance_ratio_[0]:.2%}")
    print(f"Loadings: GPU={pca.components_[0, 0]:.3f}, "
          f"API={pca.components_[0, 1]:.3f}, "
          f"Power={pca.components_[0, 2]:.3f}")


if __name__ == "__main__":
    main()