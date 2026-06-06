# Decisions Log

## 2026-06-06
- License: CC0 1.0
- Update frequency: 12h (00:00, 12:00 UTC)
- Initial weights: GPU 55% / API 30% / Power 15%

## 2026-06-06 — Phase 1 MVP launched
- 4 cloud scrapers active: AWS, Lambda Labs, CoreWeave, Azure (GCP deferred to v0.3)
- GitHub Actions automation: 12h cycle (00:00, 12:00 UTC)
- Historical raw data contains pre-filter noise (Lambda $9.86 = B200, 
  CoreWeave Unknown variant) — to be cleaned in processed layer
- Time series collection officially started

## 2026-06-06 — v0.2 launched
- Dashboard live: https://yiejun.github.io/acpi-index/
- Full automation: 5 scrapers + analysis + JSON export + GitHub Pages
- Status: data accumulation phase begins

## 2026-06-06 — v0.3 Market layer added
- Added Layer 4: NVDA + CHAT + IRBO via yfinance
- Reweighted: GPU 50 / API 27 / Power 13 / Market 10
- Rationale: cost-based layers scaled 0.91x; market sentiment given residual 10%
