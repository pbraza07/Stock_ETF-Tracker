# MarketScope v5.2 — GitHub + Render Final

MarketScope is a Streamlit stock/ETF dashboard designed for fast startup from a persistent daily snapshot.

## Included

- Nasdaq Stock Screener universe: stocks with market cap strictly above $100M.
- 229 requested ETFs from `data/etf_allowlist.csv`.
- Nasdaq stock analyst-consensus column: Strong Buy, Buy, Hold, Sell, Strong Sell.
- Color coding: Buy/Strong Buy green, Hold yellow, Sell/Strong Sell red, Not Rated gray.
- ETF analyst field is used only if Nasdaq actually exposes a genuine analyst/recommendation value; otherwise the ETF is shown as Not Rated.
- Sortable table plus advanced filters for every displayed column.
- Daily scheduled full refresh at **6:00 PM America/New_York every day**.
- All refresh/rating timestamps displayed in U.S. Eastern time.
- Manual refresh with live counter and percentage progress.
- Fast startup from `data/market_snapshot.csv` rather than downloading years of history when the page opens.
- Durable snapshot storage in GitHub; Render serves the latest deployed copy.
- Manual additions remain in the persistent snapshot and are preserved by later scheduled refreshes.

## Market data methodology

Stocks do not have NAV. Stock returns use dividend/split-adjusted total-return history. ETF performance columns use adjusted market total-return history, while current ETF NAV is displayed separately when available.

- 10Y Avg / 5Y Avg: CAGR.
- 1Y / YTD / 6M / 3M / 1M / 1D: point-to-point adjusted total return.

## Quick deployment

See `DEPLOY_GITHUB_RENDER.md`.

## v5.1 refresh-population fix

v5.1 fixes the first-refresh bootstrap problem. Earlier v5 builds could receive live quotes but leave the table blank because the live overlay required an existing non-null baseline price. Manual Refresh now downloads adjusted daily history first, calculates 10Y/5Y/1Y/YTD/6M/3M/1M/1D, then overlays the latest intraday price. A returned live quote also populates Price even when the prior snapshot price is blank. Bootstrap metadata no longer surfaces null/`None` status text, and the app falls back to a populated durable GitHub snapshot when the deployed local bootstrap file has zero populated prices.

## v5.2 returns-persistence fix

The generated files `data/default_universe.csv`, `data/market_snapshot.csv`, and `data/snapshot_metadata.json` are now **server-generated state** and are intentionally NOT bundled in this upgrade ZIP. This prevents a code upgrade from replacing a fully populated 4,000+ instrument snapshot with a blank bootstrap file.

The ZIP contains `*.bootstrap.*` fallback files only. On an existing GitHub repository, upload the v5.2 files **on top of the repository without deleting existing generated data files**. The app loads the generated local snapshot first for speed, falls back to the durable GitHub snapshot if needed, and uses the bootstrap copy only as a last resort. Manual Refresh also seeds from the durable GitHub snapshot before asking Yahoo for fresh history, so temporary Yahoo/Render throttling no longer makes saved stock return percentages disappear.
