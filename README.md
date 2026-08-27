# MarketScope v3 — Fast-start Stock & ETF Tracker

MarketScope v3 is optimized for GitHub + Render while keeping market-data retrieval free.

## Core design

- **Instant main table:** reads a precomputed local market snapshot.
- **Free data:** Yahoo Finance through `yfinance`; no paid market-data API key.
- **Daily automation:** GitHub Actions recomputes the snapshot after the U.S. market close.
- **Live button:** fetches only latest intraday prices and overlays them on the snapshot.
- **On-demand charts:** downloads chart history for one ticker only when requested.
- **Resilient:** if Yahoo is rate-limiting, the last good snapshot remains visible.

## Performance columns

Symbol, Name, Sector, Industry, Price, Since Inception, 10Y Avg, 5Y Avg, 1Y, YTD, 6M, 3M, 1M and 1D.

Positive return cells display green; negative return cells display red. The table is sortable by column.

## First deployment

See `DEPLOY_GITHUB_RENDER.md`.
