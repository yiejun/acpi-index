"""
EIA Industrial Electricity Price Scraper
Source: EIA API v2 (retail electricity prices by state)
"""
import os
import requests
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("EIA_API_KEY")
URL = "https://api.eia.gov/v2/electricity/retail-sales/data/"

# Datacenter-dense states: VA (PJM/Loudoun), TX (ERCOT),
# OR (Pacific NW hydro), IA (Midwest), CA (CAISO)
DC_STATES = ["VA", "TX", "OR", "IA", "CA"]


def fetch_prices():
    if not API_KEY:
        raise RuntimeError("EIA_API_KEY not set in .env")

    params = {
        "api_key": API_KEY,
        "frequency": "monthly",
        "data[0]": "price",
        "facets[sectorid][]": "IND",  # Industrial sector
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "offset": 0,
        "length": 60,  # last 5 years × 12 months
    }
    for s in DC_STATES:
        params.setdefault("facets[stateid][]", []).append(s) \
            if isinstance(params.get("facets[stateid][]"), list) else None

    # requests needs list-style for repeated keys — build manually
    query_states = [("facets[stateid][]", s) for s in DC_STATES]
    base_params = [(k, v) for k, v in params.items() if k != "facets[stateid][]"]
    full_params = base_params + query_states

    print(f"Fetching EIA prices for {DC_STATES}...")
    r = requests.get(URL, params=full_params, timeout=30)
    r.raise_for_status()
    return r.json()


def main():
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        data = fetch_prices()
    except Exception as e:
        print(f"Failed: {e}")
        return

    items = data.get("response", {}).get("data", [])
    print(f"Got {len(items)} data points\n")

    rows = []
    for it in items:
        price = it.get("price")
        if price is None:
            continue
        rows.append({
            "timestamp": timestamp,
            "period": it.get("period"),
            "state": it.get("stateid"),
            "state_name": it.get("stateDescription"),
            "sector": it.get("sectorid"),
            "price_cents_per_kwh": float(price),
            "price_usd_per_mwh": float(price) * 10,  # cents/kWh → $/MWh
        })

    if not rows:
        print("No data!")
        return

    df = pd.DataFrame(rows)
    print("=== Latest by state ===")
    latest = df.sort_values("period").groupby("state").tail(1)
    print(latest[["state", "period", "price_cents_per_kwh", "price_usd_per_mwh"]].to_string())

    # Save
    output_dir = Path("data/raw/power_price")
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    output_file = output_dir / f"power_price_{date_str}.parquet"
    if output_file.exists():
        existing = pd.read_parquet(output_file)
        df = pd.concat([existing, df], ignore_index=True)
    df.to_parquet(output_file, index=False)
    print(f"\n✓ Saved to {output_file}")


if __name__ == "__main__":
    main()