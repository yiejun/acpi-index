"""Quick viewer for accumulated ACPI data."""
import pandas as pd
from pathlib import Path

RAW_DIR = Path("data/raw")

def view_all():
    for provider_dir in sorted(RAW_DIR.iterdir()):
        if not provider_dir.is_dir():
            continue
        parquets = sorted(provider_dir.glob("*.parquet"))
        if not parquets:
            continue
        print(f"\n{'='*60}")
        print(f"📊 {provider_dir.name}")
        print(f"{'='*60}")
        dfs = [pd.read_parquet(p) for p in parquets]
        df = pd.concat(dfs, ignore_index=True)
        print(f"Total rows: {len(df)}")
        print(f"Time range: {df['timestamp'].min()} → {df['timestamp'].max()}")
        print(f"Unique timestamps: {df['timestamp'].nunique()}")
        if "price_per_gpu_hour_usd" in df.columns:
            print(f"Price range: ${df['price_per_gpu_hour_usd'].min():.2f} - ${df['price_per_gpu_hour_usd'].max():.2f}/GPU/hr")
        print("\nRecent 5 rows:")
        print(df.tail(5).to_string())

if __name__ == "__main__":
    view_all()