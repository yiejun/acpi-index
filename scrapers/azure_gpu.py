"""
Azure H100 GPU On-Demand Pricing Scraper
Source: Azure Retail Prices API (public, no auth)
Docs: https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices
"""
import requests
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

# Azure H100 SKU: ND96isr_H100_v5 = 8x H100 SXM5 80GB
SKU = "Standard_ND96isr_H100_v5"
GPU_COUNT = 8

API_URL = "https://prices.azure.com/api/retail/prices"
FILTER = (
    f"serviceName eq 'Virtual Machines' "
    f"and armSkuName eq '{SKU}' "
    f"and priceType eq 'Consumption'"
)


def fetch_all_pages():
    """Azure paginates with NextPageLink. Follow until done."""
    all_items = []
    url = API_URL
    params = {"$filter": FILTER, "currencyCode": "USD"}
    page = 1

    while url:
        print(f"  Fetching page {page}...")
        r = requests.get(url, params=params if page == 1 else None, timeout=30)
        r.raise_for_status()
        data = r.json()
        all_items.extend(data.get("Items", []))
        url = data.get("NextPageLink")
        page += 1
        if page > 20:  # safety limit
            print("  ⚠️ Stopped at 20 pages")
            break

    return all_items


def main():
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"Querying Azure Retail Prices API for {SKU}...")

    try:
        items = fetch_all_pages()
    except Exception as e:
        print(f"Failed: {e}")
        return

    print(f"Got {len(items)} raw items\n")

    # Filter: exclude Spot, Low Priority, Windows (keep Linux on-demand only)
    rows = []
    for it in items:
        sku_name = it.get("skuName", "")
        product = it.get("productName", "")

        # Skip Spot and Low Priority entries
        if "Spot" in sku_name or "Low Priority" in sku_name:
            continue
        # Skip Windows variants (we want Linux baseline)
        if "Windows" in product:
            continue

        price = float(it.get("retailPrice", 0))
        if price <= 0:
            continue

        rows.append({
            "timestamp": timestamp,
            "provider": "azure",
            "instance_type": it.get("armSkuName"),
            "region": it.get("armRegionName"),
            "location": it.get("location"),
            "gpu_type": "H100-SXM",
            "gpu_count": GPU_COUNT,
            "price_per_hour_usd": price,
            "price_per_gpu_hour_usd": price / GPU_COUNT,
            "pricing_type": "on-demand",
            "sku_name": sku_name,
        })

    if not rows:
        print("No on-demand H100 prices found.")
        return

    df = pd.DataFrame(rows)
    print("=== Results ===")
    print(df[["region", "price_per_hour_usd", "price_per_gpu_hour_usd"]].to_string())
    print(f"\nRegions: {df['region'].nunique()}")
    print(f"Avg per-GPU price: ${df['price_per_gpu_hour_usd'].mean():.2f}/hr")

    # Save
    output_dir = Path("data/raw/azure_gpu")
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    output_file = output_dir / f"azure_gpu_{date_str}.parquet"

    if output_file.exists():
        existing = pd.read_parquet(output_file)
        df = pd.concat([existing, df], ignore_index=True)
    df.to_parquet(output_file, index=False)
    print(f"\n✓ Saved to {output_file}")


if __name__ == "__main__":
    main()