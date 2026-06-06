"""
Lambda Labs H100 GPU Pricing Scraper
Source: lambdalabs.com/service/gpu-cloud
"""
import re
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

URL = "https://lambda.ai/pricing"
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
    """Find H100 on-demand prices, filtering out reserved/contaminated entries."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)

    pattern = re.compile(r"(H100[^\$]{0,300}?)\$\s*([\d]+\.?\d*)", re.IGNORECASE)
    results = []
    for match in pattern.finditer(text):
        context = re.sub(r"\s+", " ", match.group(1)).strip()[:200]
        price = float(match.group(2))

        # Sanity check: reasonable hourly GPU price
        if not (0.5 <= price <= 30):
            continue

        # Filter: skip cross-contamination from B200 listings
        if "B200" in context:
            continue

        # Filter: skip reserved / long-term contracts (we want on-demand)
        ctx_lower = context.lower()
        if "weeks" in ctx_lower or "year" in ctx_lower:
            continue

        # Filter: must be an actual H100 spec row (contains SXM or PCIe)
        if "SXM" not in context and "PCIe" not in context:
            continue

        # Identify variant
        variant = "H100-SXM" if "SXM" in context else "H100-PCIe"

        results.append({
            "context": context,
            "price": price,
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

    # Save raw HTML for debugging
    debug_dir = Path("data/raw/lambda_gpu")
    debug_dir.mkdir(parents=True, exist_ok=True)
    debug_path = debug_dir / "debug_raw.html"
    debug_path.write_text(html, encoding="utf-8")
    print(f"Raw HTML saved to {debug_path}")

    matches = extract_h100_prices(html)
    print(f"\nFound {len(matches)} H100 price candidates:")
    for m in matches:
        print(f"  ${m['price']:.2f}  ← {m['context'][:100]}")

    if not matches:
        print("\n⚠️  No H100 prices found. Page may be JS-rendered.")
        print("   Open debug_raw.html in browser to inspect.")
        return

    rows = []
    for m in matches:
        rows.append({
            "timestamp": timestamp,
            "provider": "lambda_labs",
            "gpu_type": m["variant"],   # ← 이 줄 추가/변경
            "price_per_gpu_hour_usd": m["price"],
            "pricing_type": "on-demand",
            "context": m["context"],
        })
    
    df = pd.DataFrame(rows)
    print("\n=== Results ===")
    print(df.to_string())

    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    output_file = debug_dir / f"lambda_gpu_{date_str}.parquet"
    if output_file.exists():
        existing = pd.read_parquet(output_file)
        df = pd.concat([existing, df], ignore_index=True)
    df.to_parquet(output_file, index=False)
    print(f"\n✓ Saved to {output_file}")


if __name__ == "__main__":
    main()