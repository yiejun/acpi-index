"""Export processed data to JSON for the dashboard."""
import json
import pandas as pd
from pathlib import Path

PROCESSED = Path("data/processed")
DOCS = Path("docs")


def df_to_records(df):
    """Convert DataFrame to JSON-safe records (handles dates, NaN)."""
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == "object":
            out[col] = out[col].astype(str)
    return json.loads(out.to_json(orient="records", date_format="iso"))


def main():
    DOCS.mkdir(exist_ok=True)

    payload = {"layers": {}, "snapshots": [], "zscores": [], "meta": {}}

    snap = PROCESSED / "acpi_snapshots.parquet"
    if snap.exists():
        df = pd.read_parquet(snap).sort_values("timestamp")
        payload["snapshots"] = df_to_records(df)
        if not df.empty:
            payload["meta"]["latest_date"] = str(df["date"].max())

    z = PROCESSED / "acpi_zscores.parquet"
    if z.exists():
        df = pd.read_parquet(z).sort_values("timestamp")
        payload["zscores"] = df_to_records(df)

    for name in ["gpu", "api", "power"]:
        p = PROCESSED / f"{name}_daily.parquet"
        if p.exists():
            df = pd.read_parquet(p).sort_values("date")
            payload["layers"][name] = df_to_records(df)
    
    corr = PROCESSED / "acpi_correlations.parquet"
    if corr.exists():
        df = pd.read_parquet(corr).sort_values("date")
        payload["correlations"] = df_to_records(df)

    pca = PROCESSED / "acpi_pca.parquet"
    if pca.exists():
        df = pd.read_parquet(pca).sort_values("date")
        payload["pca"] = df_to_records(df)

    level = PROCESSED / "acpi_level.parquet"
    if level.exists():
        df = pd.read_parquet(level).sort_values("date")
        payload["level"] = df_to_records(df)
        if not df.empty:
            last = df.iloc[-1]
            payload["meta"]["acpi_level"] = float(last["acpi_level"])
            payload["meta"]["acpi_level_chg_1d"] = float(last["chg_1d_pct"])


    out = DOCS / "data.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"✓ Exported to {out}")

    


if __name__ == "__main__":
    main()