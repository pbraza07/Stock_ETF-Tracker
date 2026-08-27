# MarketScope v5 — GitHub + Render Final

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
