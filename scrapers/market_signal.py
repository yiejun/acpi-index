"""
Market Signal Layer — NVDA + AI ETFs
Source: yfinance (Yahoo Finance, no auth)
"""
import yfinance as yf
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

TICKERS = ["NVDA", "CHAT", "IRBO"]


def main():
    timestamp = datetime.now(timezone.utc).isoformat()
    rows = []

    for ticker in TICKERS:
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d", interval="1d")
            if hist.empty:
                print(f"  ⚠️  {ticker}: no data")
                continue
            latest = hist.iloc[-1]
            prev = hist.iloc[-2] if len(hist) > 1 else latest
            close = float(latest["Close"])
            prev_close = float(prev["Close"])
            pct_change = (close - prev_close) / prev_close * 100 if prev_close else 0

            print(f"  {ticker}: ${close:.2f} ({pct_change:+.2f}%)")
            rows.append({
                "timestamp": timestamp,
                "ticker": ticker,
                "close_usd": close,
                "prev_close_usd": prev_close,
                "pct_change_1d": pct_change,
                "volume": int(latest["Volume"]),
            })
        except Exception as e:
            print(f"  Failed {ticker}: {e}")

    if not rows:
        print("No data!")
        return

    df = pd.DataFrame(rows)
    output_dir = Path("data/raw/market_signal")
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    output_file = output_dir / f"market_signal_{date_str}.parquet"
    if output_file.exists():
        existing = pd.read_parquet(output_file)
        df = pd.concat([existing, df], ignore_index=True)
    df.to_parquet(output_file, index=False)
    print(f"\n✓ Saved to {output_file}")


if __name__ == "__main__":
    main()