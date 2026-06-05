"""
CoreWeave H100 GPU On-Demand Pricing Scraper
Source: coreweave.com/pricing
"""
import re
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

URL = "https://www.coreweave.com/pricing"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def fetch_html():
    print(f"Fetching {URL}...")
    r = requests.get(URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def extract_h100_prices(html):
    """Find H100 on-demand prices in CoreWeave page text."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)

    pattern = re.compile(r"(H100[^\$]{0,300}?)\$\s*([\d,]+\.?\d*)", re.IGNORECASE)
    results = []
    for match in pattern.finditer(text):
        context = re.sub(r"\s+", " ", match.group(1)).strip()[:200]
        price_str = match.group(2).replace(",", "")
        price = float(price_str)

        # Skip cross-contamination (other GPU types in context)
        if any(x in context for x in ["B200", "GB200", "H200", "A100"]):
            continue

        # Reasonable per-GPU-hour OR per-node-hour range
        # Per-GPU: $2-8, Per-8-GPU-node: $20-60
        if not (1.0 <= price <= 60.0):
            continue

        # Determine variant
        if "HGX" in context or "SXM" in context:
            variant = "H100-HGX"
        elif "PCIe" in context or "PCIE" in context:
            variant = "H100-PCIe"
        elif re.search(r"H100\s+8\s+80", context):
            # CoreWeave config: "H100 8 80 ..." = 8 GPUs × 80GB VRAM = HGX node
            variant = "H100-HGX"
        else:
            variant = "H100-Unknown"

        # If price > $20, likely per-node (8 GPUs); normalize to per-GPU
        per_gpu_price = price / 8 if price > 20 else price

        results.append({
            "context": context,
            "raw_price": price,
            "price_per_gpu_hour_usd": per_gpu_price,
            "variant": variant,
        })
    return results


def main():
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        html = fetch_html()
    except Exception as e:
        print(f"Failed to fetch: {e}")
        return

    print(f"Got {len(html)} bytes")

    debug_dir = Path("data/raw/coreweave_gpu")
    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / "debug_raw.html").write_text(html, encoding="utf-8")
    print(f"Raw HTML saved to {debug_dir / 'debug_raw.html'}")

    matches = extract_h100_prices(html)
    print(f"\nFound {len(matches)} H100 price candidates:")
    for m in matches:
        print(f"  ${m['raw_price']:>7.2f} → ${m['price_per_gpu_hour_usd']:.2f}/GPU "
              f"[{m['variant']}]  ← {m['context'][:80]}")

    if not matches:
        print("\n⚠️  No H100 prices found. Check debug_raw.html.")
        return

    rows = []
    for m in matches:
        rows.append({
            "timestamp": timestamp,
            "provider": "coreweave",
            "gpu_type": m["variant"],
            "price_per_gpu_hour_usd": m["price_per_gpu_hour_usd"],
            "raw_listed_price_usd": m["raw_price"],
            "pricing_type": "on-demand",
            "context": m["context"],
        })

    df = pd.DataFrame(rows)
    # Prefer specific variants (HGX/PCIe) over Unknown when prices match
    df["_priority"] = df["gpu_type"].apply(lambda x: 1 if x == "H100-Unknown" else 0)
    df = df.sort_values("_priority").drop(columns="_priority")
    # Dedupe by price (keeps first = most specific variant)
    df = df.drop_duplicates(subset=["provider", "price_per_gpu_hour_usd"], keep="first").reset_index(drop=True)

    print("\n=== Results ===")
    print(df.to_string())

    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    output_file = debug_dir / f"coreweave_gpu_{date_str}.parquet"
    if output_file.exists():
        existing = pd.read_parquet(output_file)
        df = pd.concat([existing, df], ignore_index=True)
    df.to_parquet(output_file, index=False)
    print(f"\n✓ Saved to {output_file}")


if __name__ == "__main__":
    main()