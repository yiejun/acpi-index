"""
Vast.ai Marketplace H100 Pricing Scraper
Source: Vast.ai authenticated bundles API
- on-demand price (dph_total)
- interruptible price (min_bid) — closest to AWS "spot"
"""
import os
import requests
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("VAST_API_KEY")
URL = "https://console.vast.ai/api/v0/bundles/"


def fetch_bundles():
    if not API_KEY:
        raise RuntimeError("VAST_API_KEY not set")
    headers = {"Authorization": f"Bearer {API_KEY}"}
    # Query: any GPU, we filter H100 in code
    params = {"q": '{"verified": {"eq": true}, "external": {"eq": false}}'}
    r = requests.get(URL, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("offers", [])


def main():
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        offers = fetch_bundles()
    except Exception as e:
        print(f"Failed: {e}")
        return

    print(f"Got {len(offers)} verified offers\n")

    # Filter H100 only
    h100_offers = [o for o in offers if "H100" in (o.get("gpu_name") or "")]
    print(f"H100 offers: {len(h100_offers)}\n")

    if not h100_offers:
        print("No H100 offers!")
        return

    rows = []
    for o in h100_offers:
        gpu_name = o.get("gpu_name", "")
        n_gpus = o.get("num_gpus", 1) or 1
        dph_total = o.get("dph_total")  # on-demand $/hr
        min_bid = o.get("min_bid")       # interruptible $/hr

        # Normalize variant name
        if "SXM" in gpu_name:
            variant = "H100-SXM"
        elif "NVL" in gpu_name:
            variant = "H100-NVL"
        elif "PCIE" in gpu_name or "PCIe" in gpu_name:
            variant = "H100-PCIe"
        else:
            variant = "H100-Unknown"

        rows.append({
            "timestamp": timestamp,
            "provider": "vast_ai",
            "gpu_type": variant,
            "n_gpus": n_gpus,
            "ondemand_per_gpu_hour_usd": (dph_total / n_gpus) if dph_total else None,
            "interruptible_per_gpu_hour_usd": (min_bid / n_gpus) if min_bid else None,
            "reliability": o.get("reliability"),
            "region": o.get("geolocation"),
        })

    df = pd.DataFrame(rows)

    # Aggregate: market median per variant + pricing type
    print("=== Market summary ===")
    summary = df.groupby("gpu_type").agg(
        n_offers=("provider", "count"),
        ondemand_median=("ondemand_per_gpu_hour_usd", "median"),
        ondemand_min=("ondemand_per_gpu_hour_usd", "min"),
        interruptible_median=("interruptible_per_gpu_hour_usd", "median"),
        interruptible_min=("interruptible_per_gpu_hour_usd", "min"),
    ).round(3)
    print(summary.to_string())

    output_dir = Path("data/raw/vast_gpu")
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    output_file = output_dir / f"vast_gpu_{date_str}.parquet"
    if output_file.exists():
        existing = pd.read_parquet(output_file)
        df = pd.concat([existing, df], ignore_index=True)
    df.to_parquet(output_file, index=False)
    print(f"\n✓ Saved {len(rows)} offers to {output_file}")


if __name__ == "__main__":
    main()