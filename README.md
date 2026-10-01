# ACPI — AI Compute Price Index, v1.0

A daily fixed-basket quote-price index for AI compute. GPU rental and API inference prices enter ACPI; equities and monthly industrial electricity are separate context. No invented tick movement, PCA price weighting, or claims of a live trading feed.

## Run locally

Requires Python 3.11+.

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m analysis.build_dashboard
python -m http.server 8000 --directory docs
```

Optional DOM interaction checks (Node 20.19+): `npm install` then `npm test`. These check behavior without claiming a full browser visual review.

Open `http://localhost:8000`. Serve the folder over HTTP: opening the dashboard's `index.html` directly cannot fetch JSON reliably. `docs/methodology.html` explains the formulas and includes an interactive numeric example.

## Apply this update to the existing GitHub repository

1. Make a backup or a branch of your current checkout.
2. Copy the contents of the supplied `acpi-index` folder into your existing repository root, including the hidden `.github` folder. Keep your existing `.git` directory and any local `.env` file.
3. Run the tests and build commands above. Keep the supplied `analysis/basket.json`; it fixes the historical base and membership.
4. Review and commit the changes, then push to `main`:

```bash
git add README.md analysis scripts tests scrapers docs .github/workflows/scrape.yml data/processed/acpi_level.parquet data/processed/basket_daily.parquet
git commit -m "Fix ACPI methodology and redesign price dashboard"
git push origin main
```

GitHub Pages should continue publishing from `main` / `docs`. In Actions, manually run **Update ACPI quotes** once. Existing `EIA_API_KEY` and `VAST_API_KEY` secrets stay in GitHub; this update does not contain credentials. Required compute sources use public APIs/pages. The new schedule is every two hours at minute 17, with serialized writers. GitHub scheduled runs can be delayed.

## Fixed basket and methodology

- Composite: fixed 70% GPU / 30% API geometric price-relative index. These are project-chosen weights, not global spending shares.
- GPU: equal provider shares across AWS, Lambda, CoreWeave and Azure; each provider's fixed configuration/region quotes split its share equally.
- API: GPT-4o, Claude Sonnet 4.6, Gemini 2.5 Flash; equal model shares, 2:1 input/output tokens, per million total tokens.
- `analysis/basket.json` records base date, original quote identifiers, prices, membership and weights. Builds reuse it. Missing constituents never cause silent reweighting.
- Daily UTC close = last collected quote for each item that day. Current UTC day is provisional. Gaps carry for at most seven calendar days, explicitly labeled; expired quotes suppress the index.
- Statistics use calendar-day series, not scraper counts. Flat prices produce flat charts. Undefined z-scores/correlation/PCA are shown as unavailable.
- Power source months are retained per collected day and state. Equities retain individual closes; new records include actual quote dates, old missing quote dates are labeled.
- GPU bundles differ in host resources; API models differ in capability. The series measures like-for-like quote changes, not identical output performance or achieved transaction costs.

## Historical rebuild result

For the supplied raw data, all 13 chosen fixed quotes have unchanged recorded prices from the 2026-06-05 base through 2026-10-01. Rebuilding gives a level of 100 throughout. Earlier large daily moves disappear when provider weights and quote membership are held fixed. This is a result of the saved quotes, not independently audited historical tariffs. Collect more variable spot quotes or introduce a separately versioned performance-adjusted index if that is the desired future scope.

## Pipeline

`python -m analysis.build_dashboard` is the authoritative build. It reconstructs history from raw Parquet, exports `docs/data.json`, and writes `acpi_level.parquet` and `basket_daily.parquet`. Previous analysis entry points delegate to it so the old calculation cannot accidentally overwrite v1. Older processed snapshot/PCA files remain historical artifacts and are not read by v1.

The workflow permits individual scrapers to finish independently, then requires tests/build plus a freshness check for every required provider. It persists the dashboard's explicit incomplete status even when expired quotes make the build fail; optional market/power collection is labeled by date in the UI. A passed workflow proves checks passed, not independent pricing accuracy.

Constituent replacement needs a reviewed new basket version and overlap linking. Do not remove the manifest to silently reset the base or drop a retired model.
