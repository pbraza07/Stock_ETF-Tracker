# MarketScope v5.3 — Nasdaq >$100B + Button Filters

MarketScope is a Streamlit stock/ETF dashboard designed for fast startup from a persistent daily snapshot.

## What changed in v5.3

- **Nasdaq stock universe:** only stocks returned by the direct Nasdaq Stock Screener with market capitalization strictly above **$100 billion**.
- The previous unofficial mirror fallback was removed: the automatic stock universe is now **Nasdaq Stock Screener only**.
- The requested ETF allowlist remains included.
- Explicitly manual/persistent symbol additions remain preserved even when they are outside the automatic >$100B screen.
- Main filters are now clickable **segmented buttons / pills** instead of dropdowns:
  - Instrument
  - Stock market-cap tier
  - Analyst Rating
  - Sector
- Advanced categorical filters also use clickable pills when practical.
- Removed these columns from the main table:
  - Return Basis
  - Rating Source
  - Data As Of
  - Rating Updated ET
  - Snapshot Updated ET
- **Rating update** and **Snapshot update** are shown once in a status strip immediately above the table, using U.S. Eastern time.
- Table text is larger and rows are taller for easier reading.

## Existing behavior retained

- Nasdaq stock analyst consensus: Strong Buy, Buy, Hold, Sell, Strong Sell.
- Rating colors: Buy/Strong Buy green, Hold yellow, Sell/Strong Sell red, Not Rated gray.
- Sortable table plus filters across displayed columns.
- Daily full refresh at **6:00 PM America/New_York every calendar day**.
- Manual refresh with live count and percentage progress.
- Fast startup from the last persistent snapshot.
- Durable GitHub snapshot storage; Render serves the latest deployed copy.
- Manual additions remain persistently tracked when GitHub manual-save is configured.

## Return methodology

Stocks do not have NAV. Stock returns use dividend/split-adjusted total-return history. ETF performance columns use adjusted market total-return history, while current ETF NAV is displayed separately when available.

- 10Y Avg / 5Y Avg: CAGR.
- 1Y / YTD / 6M / 3M / 1M / 1D: point-to-point adjusted total return.

## Upgrade safety

The generated files below are server-generated state and are intentionally **not** included in this upgrade ZIP:

- `data/default_universe.csv`
- `data/market_snapshot.csv`
- `data/snapshot_metadata.json`

Upload v5.3 on top of the existing GitHub repository without deleting those files first. The new app immediately hides legacy automatic stocks under $100B, and the next scheduled/manual GitHub refresh rewrites the generated universe to Nasdaq >$100B only.

See `DEPLOY_GITHUB_RENDER.md` and `IMPORTANT_UPGRADE_v5.3.md`.
