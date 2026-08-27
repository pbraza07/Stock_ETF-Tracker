# MarketScope v5.4.2 — Stock-Only Sector Filters & Larger Table

MarketScope is a Streamlit stock/ETF tracker designed for GitHub + Render. The automatic stock universe comes from the direct Nasdaq Stock Screener and keeps only stocks with market capitalization strictly above **$100 billion**, plus the requested ETF allowlist and explicitly manual persistent additions.

## v5.4.2 changes

- Sector filter buttons are generated from **stock sectors only**; ETF-only sector/category labels are hidden from the sector button list.
- **NAV** was removed from the main table.
- Main-table data font increased to **19px**, symbols to **21px bold**, and row height to **54px** for better readability.
- Mobile-specific table typography keeps data legible instead of shrinking it; horizontal scrolling is used when needed.
- Existing v5.4 return ordering, buy signals, persistence, and 6:00 PM Eastern daily refresh are preserved.

## v5.4 base features

- Main performance columns are now ordered exactly: **1D, 1M, 3M, 6M, YTD, 1Y Avg, 3Y Avg, 5Y Avg, 10Y Avg**.
- **3Y Avg** was added and is calculated as annualized CAGR from adjusted daily history.
- **1Y Avg** is now calculated as annualized 1-year return; older snapshots migrate their prior 1Y value until the next refresh computes it exactly.
- The main table no longer shows **Inception Date** or **Exchange**. Since-inception data may remain in the backend for compatibility but is not shown in the table.
- All main-table columns use Streamlit content-fit sizing instead of fixed small/medium widths.
- Existing larger table typography remains enabled.
- New rule-based **Short Buy** and **Long Buy** signals are generated during scheduled and manual refreshes.
- A Nasdaq **Strong Buy** consensus is treated as a fundamental/consensus buy signal for stocks. ETFs use technical signals because Nasdaq's public ETF screener generally does not provide stock-style analyst consensus.
- New signal transitions are saved in the persistent snapshot using `Short Signal New` / `Long Signal New`; the app shows a Buy Signal Alerts panel on startup.
- Daily refresh remains **6:00 PM America/New_York every calendar day**.
- Manual refresh still shows processed count and percentage and saves to GitHub when `MARKETSCOPE_GITHUB_TOKEN` is configured in Render.

## Signal rules

**Short Buy (technical):** uses price vs SMA20, SMA20 vs SMA50, MACD vs signal line, RSI14 in a bullish 50–70 range, and positive 1M/3M momentum. A signal requires at least 5 of 6 conditions and is suppressed by Nasdaq Sell/Strong Sell ratings.

**Long Buy:** long-trend technical conditions use price above SMA200, SMA50 above SMA200, and positive 6M / 1Y Avg / 3Y Avg / 5Y Avg evidence. For stocks, Nasdaq Buy/Strong Buy consensus confirms a long technical signal; Nasdaq Strong Buy alone is also treated as a fundamental/consensus buy signal. ETFs use the technical long signal.

Signals are informational screeners, not investment advice or guarantees.

## Persistent generated files

Do **not** delete these existing GitHub-generated files when upgrading:

- `data/default_universe.csv`
- `data/market_snapshot.csv`
- `data/snapshot_metadata.json`

The ZIP intentionally ships only `*.bootstrap.*` fallback files so an upgrade does not overwrite the last good server snapshot.

See `DEPLOY_GITHUB_RENDER.md` and `IMPORTANT_UPGRADE_v5.4.md`.
