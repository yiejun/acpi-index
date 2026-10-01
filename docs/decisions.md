# v1.0 decisions

- Replace changing PCA provider weights with committed fixed quote membership.
- Separate compute prices from equities and electricity context.
- Use fixed geometric price ratios, correctly named; no Törnqvist claim.
- Rebuild saved daily history from last per-item quote instead of uneven scrape averages.
- Daily calendar-day statistics, explicit carry/expiry, provisional current-day closes.
- Source month and quote date differ from collection timestamps.
- Deterministic dependency-free SVG charts: range selection, crosshair, comparison, rebase, MA30, CSV export.
- No candles or artificial tick movement on a daily quote series.
