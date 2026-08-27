# MarketScope — Stock & ETF Performance Tracker (GitHub + Render Edition)

A polished Streamlit dashboard for stocks and ETFs by sector, using Yahoo Finance through the open-source `yfinance` client. **No paid market-data API key is required.** This edition is preconfigured for GitHub + Render deployment.

## Dashboard features

- Symbol, Name, Sector, Industry and latest available Price
- Since Inception cumulative performance
- 10-year average annual performance (CAGR)
- 5-year average annual performance (CAGR)
- 1-year, YTD, 6-month, 3-month, 1-month and 1-day performance
- Green positive / red negative performance cells
- Sortable table columns
- Sector and stock/ETF filters
- Yahoo ticker/company search
- Add/remove tracker symbols
- Manual intraday **Refresh live prices**
- 24-hour historical-data cache / daily refresh while open
- Detail chart with 1M / 6M / 1Y / 5Y / MAX ranges
- No Twelve Data, Polygon/Massive, Alpha Vantage, or other paid market-data API dependency

## GitHub + Render deployment

This repository includes:

- `render.yaml` — Render Blueprint configuration
- `.python-version` — selects Python 3.12 on Render
- `requirements.txt` — deploy dependencies
- `Procfile` — fallback production start command
- `.gitignore` — prevents local runtime files/secrets from being committed
- `DEPLOY_GITHUB_RENDER.md` — detailed deployment procedure

### Fast deployment

1. Upload the contents of this folder to the root of a GitHub repository.
2. In Render select **New > Blueprint**.
3. Connect that GitHub repository.
4. Render detects `render.yaml` and creates the Free Python web service.
5. Apply/deploy the Blueprint.
6. Open the generated `onrender.com` URL.

See `DEPLOY_GITHUB_RENDER.md` for detailed steps and the manual Web Service settings.

## Render-safe watchlist behavior

Render Free uses ephemeral local storage. To avoid pretending that server-side file changes are permanent:

- the committed `data/watchlist.json` is the default tracker seed;
- local desktop launches save your customized list to `data/watchlist.local.json` (ignored by Git);
- Render sessions keep customization in Streamlit session state and mirror the symbol list into the URL, so you can bookmark the customized URL.

## Local launch

### Windows

Double-click `start_windows.bat`.

### macOS

Run `./start_mac.command`.

### Linux

Run `./start_linux.sh`.

### Manual

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Performance methodology

Historical daily prices are requested with `auto_adjust=True`, and the requested returns are calculated locally.

- **Since Inception:** current/latest price ÷ first available adjusted close − 1
- **10Y Avg / 5Y Avg:** CAGR (annualized compounded return)
- **1Y / 6M / 3M / 1M:** point-to-point adjusted return using the nearest available prior trading date
- **YTD:** return versus the last trading close before January 1
- **1D:** latest/current price versus the prior trading close

If the ticker does not have enough history for a 5-year or 10-year CAGR, the dashboard leaves that result blank.

## Data-source and licensing note

This project uses Yahoo Finance through `yfinance`; it does not directly scrape Yahoo Finance or Investing.com HTML. No API key is required. Availability, delay status, and rate limits can vary. Free public market-data sources cannot guarantee identical order-critical prices to every broker or consolidated exchange feed.

For personal/research use, review Yahoo Finance/yfinance terms that apply to your use. If you later turn the app into a public commercial data product, review data redistribution/licensing requirements before doing so.
