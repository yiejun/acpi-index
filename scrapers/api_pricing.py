"""
API Token Pricing Scraper
Source: OpenRouter Models API (public, no auth, pass-through pricing)
"""
import requests
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

URL = "https://openrouter.ai/api/v1/models"

# Track representative models from each major provider
# These are the "workhorse" and "flagship" tier models that drive API cost signal
TRACKED_MODELS = {
    # OpenAI
    "openai/gpt-4o": ("openai", "workhorse"),
    "openai/gpt-4o-mini": ("openai", "budget"),
    "openai/gpt-5.4": ("openai", "flagship"),
    "openai/gpt-5.5": ("openai", "flagship"),
    # Anthropic
    "anthropic/claude-sonnet-4.6": ("anthropic", "workhorse"),
    "anthropic/claude-opus-4.6": ("anthropic", "flagship"),
    "anthropic/claude-opus-4.7": ("anthropic", "flagship"),
    "anthropic/claude-haiku-4.5": ("anthropic", "budget"),
    # Google
    "google/gemini-2.5-flash": ("google", "workhorse"),
    "google/gemini-2.5-pro": ("google", "flagship"),
}


def fetch_models():
    print(f"Fetching {URL}...")
    r = requests.get(URL, timeout=30)
    r.raise_for_status()
    return r.json().get("data", [])


def main():
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        models = fetch_models()
    except Exception as e:
        print(f"Failed: {e}")
        return

    print(f"Got {len(models)} total models\n")

    rows = []
    found_ids = set()
    for m in models:
        model_id = m.get("id", "")
        if model_id not in TRACKED_MODELS:
            continue

        provider, tier = TRACKED_MODELS[model_id]
        pricing = m.get("pricing", {})

        # OpenRouter prices are per-token strings. Convert to per-million.
        try:
            prompt_per_token = float(pricing.get("prompt", 0))
            completion_per_token = float(pricing.get("completion", 0))
        except (TypeError, ValueError):
            continue

        if prompt_per_token <= 0 or completion_per_token <= 0:
            continue

        input_per_m = prompt_per_token * 1_000_000
        output_per_m = completion_per_token * 1_000_000

        rows.append({
            "timestamp": timestamp,
            "provider": provider,
            "model_id": model_id,
            "model_name": m.get("name", ""),
            "tier": tier,
            "input_price_per_million_usd": input_per_m,
            "output_price_per_million_usd": output_per_m,
            "context_length": m.get("context_length"),
        })
        found_ids.add(model_id)

    # Report missing tracked models (may have been deprecated/renamed)
    missing = set(TRACKED_MODELS) - found_ids
    if missing:
        print(f"⚠️  Not found on OpenRouter: {missing}")

    if not rows:
        print("No tracked models found!")
        return

    df = pd.DataFrame(rows)
    print("=== Results ===")
    print(df[["provider", "model_id", "tier",
              "input_price_per_million_usd",
              "output_price_per_million_usd"]].to_string())

    # Save
    output_dir = Path("data/raw/api_pricing")
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    output_file = output_dir / f"api_pricing_{date_str}.parquet"
    if output_file.exists():
        existing = pd.read_parquet(output_file)
        df = pd.concat([existing, df], ignore_index=True)
    df.to_parquet(output_file, index=False)
    print(f"\n✓ Saved to {output_file}")


if __name__ == "__main__":
    main()