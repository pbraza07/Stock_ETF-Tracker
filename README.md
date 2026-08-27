# MarketScope v4 — Large Universe / GitHub + Render

MarketScope is a Streamlit stock & ETF performance dashboard designed to deploy from GitHub to Render without a paid market-data API key.

## v4 changes

- Dynamic U.S. stock universe: market capitalization **> $100 million**.
- 229 explicitly requested ETFs stored in `data/etf_allowlist.csv`.
- `data/default_universe.csv` is rebuilt automatically from the free Nasdaq stock screener source and the ETF allowlist.
- GitHub Actions precomputes the expensive performance snapshot so the Render app opens from a local CSV instead of downloading years of history at page load.
- Return columns: 10Y Avg, 5Y Avg, 1Y, YTD, 6M, 3M, 1M, 1D.
- Positive returns are green; negative returns are red; columns are sortable.
- Search first checks the local full universe; Yahoo search is only used for symbols outside the universe.
- Live refresh requests only the symbols currently shown after filters.
- ETF current NAV can be loaded on demand when Yahoo publishes `navPrice`.
- A visible **Return Basis** column prevents market-price history from being mislabeled as NAV history.

## Important NAV terminology

Stocks do not have NAV. The performance columns use adjusted total-return history. ETFs use adjusted **market** total-return history in the main table; current ETF NAV is shown separately when available. See `RETURN_METHODOLOGY.md`.

## Key files

- `app.py` — Streamlit dashboard
- `analytics.py` — return calculations
- `providers/yahoo.py` — Yahoo/yfinance provider
- `scripts/update_universe.py` — builds $100M+ stock universe + ETF allowlist
- `scripts/update_snapshot.py` — builds daily adjusted-return snapshot
- `data/default_universe.csv` — generated universe
- `data/etf_allowlist.csv` — requested ETF symbols
- `.github/workflows/update_market_snapshot.yml` — automated daily refresh
- `render.yaml` — Render deployment configuration

## First deployment

1. Upload all files to the root of a GitHub repository.
2. Open the repository **Actions** tab.
3. Run **Refresh MarketScope universe and snapshot** once. A normal push to `main` also starts it automatically.
4. Wait for the action to commit the generated universe and snapshot.
5. Create a Render **Blueprint** from the repository. Render reads `render.yaml`.
6. Once deployed, the app opens from the committed snapshot immediately after the Render service itself is awake.

The scheduled GitHub workflow runs on weekdays at 23:15 UTC, safely after the regular U.S. market close throughout the year.

## Local run

Windows: double-click `start_windows.bat`.

Or run:

```bash
pip install -r requirements.txt
python scripts/update_universe.py
python scripts/update_snapshot.py
streamlit run app.py
```

## Free-data limitations

Yahoo/yfinance can be delayed or rate-limited and is intended for personal/research use subject to Yahoo's terms. A free web source cannot guarantee the same consolidated exchange feed as every broker. ETF historical NAV is not universally exposed as a standardized free Yahoo time series.

## v4 Large-Universe policy

The packaged CSV is a deployment bootstrap. On the first GitHub Action run (and on each scheduled refresh), `scripts/update_universe.py` replaces it with the current Nasdaq-screened U.S. stock universe whose market capitalization is strictly greater than $100,000,000, then merges the 229 explicitly requested ETFs from `data/etf_allowlist.csv`. This design prevents the repository from permanently freezing a market-cap screen that becomes stale as prices and shares outstanding change.
