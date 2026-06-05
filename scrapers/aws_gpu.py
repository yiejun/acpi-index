"""
AWS H100 GPU On-Demand Pricing Scraper
Source: AWS public pricing JSON (no auth required)
"""
import os
import tempfile
import requests
import ijson
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

# H100 instances on AWS: p5.48xlarge has 8x H100 80GB
H100_INSTANCES = {"p5.48xlarge": 8}
REGIONS = ["us-east-1", "us-west-2"]

BASE_URL = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/{region}/index.json"


def download_pricing(region):
    """Stream-download AWS pricing JSON to a temp file."""
    url = BASE_URL.format(region=region)
    print(f"[{region}] Downloading pricing JSON (this can take several minutes)...")

    response = requests.get(url, stream=True, timeout=600)
    response.raise_for_status()

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
    total_mb = 0
    for chunk in response.iter_content(chunk_size=1024 * 1024):
        tmp.write(chunk)
        total_mb += 1
        if total_mb % 100 == 0:
            print(f"  ...{total_mb} MB downloaded")
    tmp.close()
    print(f"[{region}] Downloaded {total_mb} MB total")
    return tmp.name


def find_skus(json_path):
    """Pass 1: find SKUs matching our H100 instances (Linux/Shared/OnDemand)."""
    matched = {}
    with open(json_path, "rb") as f:
        for sku, product in ijson.kvitems(f, "products"):
            attrs = product.get("attributes", {})
            it = attrs.get("instanceType")
            if (it in H100_INSTANCES
                and attrs.get("tenancy") == "Shared"
                and attrs.get("operatingSystem") == "Linux"
                and attrs.get("preInstalledSw") == "NA"
                and attrs.get("capacitystatus") == "Used"):
                matched[sku] = {
                    "instance_type": it,
                    "gpu_count": H100_INSTANCES[it],
                    "location": attrs.get("location"),
                }
    return matched


def find_prices(json_path, matched_skus):
    """Pass 2: extract OnDemand prices for matched SKUs."""
    rows = []
    with open(json_path, "rb") as f:
        for sku, terms in ijson.kvitems(f, "terms.OnDemand"):
            if sku not in matched_skus:
                continue
            info = matched_skus[sku]
            for _, term in terms.items():
                for _, dim in term.get("priceDimensions", {}).items():
                    price = float(dim.get("pricePerUnit", {}).get("USD", 0))
                    if price > 0:
                        rows.append({
                            "instance_type": info["instance_type"],
                            "location": info["location"],
                            "gpu_count": info["gpu_count"],
                            "price_per_hour_usd": price,
                        })
    return rows


def main():
    timestamp = datetime.now(timezone.utc).isoformat()
    all_rows = []

    for region in REGIONS:
        json_path = None
        try:
            json_path = download_pricing(region)
            print(f"[{region}] Parsing products...")
            skus = find_skus(json_path)
            print(f"[{region}] Found {len(skus)} matching SKUs")
            print(f"[{region}] Parsing prices...")
            prices = find_prices(json_path, skus)
            for r in prices:
                all_rows.append({
                    "timestamp": timestamp,
                    "provider": "aws",
                    "instance_type": r["instance_type"],
                    "region": r["location"],
                    "gpu_type": "H100-80GB",
                    "gpu_count": r["gpu_count"],
                    "price_per_hour_usd": r["price_per_hour_usd"],
                    "price_per_gpu_hour_usd": r["price_per_hour_usd"] / r["gpu_count"],
                    "pricing_type": "on-demand",
                })
        except Exception as e:
            print(f"[{region}] ERROR: {e}")
        finally:
            if json_path and os.path.exists(json_path):
                os.unlink(json_path)

    if not all_rows:
        print("No data collected!")
        return

    df = pd.DataFrame(all_rows)
    print("\n=== Results ===")
    print(df.to_string())

    # Save to parquet (append by date)
    output_dir = Path("data/raw/aws_gpu")
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    output_file = output_dir / f"aws_gpu_{date_str}.parquet"

    if output_file.exists():
        existing = pd.read_parquet(output_file)
        df = pd.concat([existing, df], ignore_index=True)

    df.to_parquet(output_file, index=False)
    print(f"\n✓ Saved to {output_file}")


if __name__ == "__main__":
    main()