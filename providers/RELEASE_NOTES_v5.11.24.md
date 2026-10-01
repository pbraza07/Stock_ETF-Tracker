# MarketScope v5.11.24

- Restores the Investing.com iframe to the main dashboard using the same widget URL options, dimensions, dark color filter and source footer as v5.11.20.
- United States only, three-star importance, weekly view and Eastern Time default remain configured.
- Dashboard calendar rendering no longer depends on server-side event collection, API credentials or a local calendar cache. Browser/provider restrictions can still affect iframe loading.
- Adds SAHMREALTIME alongside USPHCI and RECPROUSM156N in the Recession Indicators tab. All three remain native dark Plotly charts with source names, descriptions, observation dates, history controls and CSV downloads.
- The Sahm chart uses percentage points, a 0.50 threshold line and a triggered/not-triggered status. It explains that the indicator is not a probability or an official recession declaration. The smoothed-probability chart retains its independent 0–100% scale.
- FRED API requests use realtime_start=1990-07-04 and realtime_end=9999-12-31. FRED_API_KEY remains a Render environment variable / GitHub Actions secret; no key is included in the archive.
- The snapshot workflow now collects all three FRED series and no longer attempts calendar scraping. Earlier stored calendar snapshots are preserved but are not used by the dashboard iframe.

Deploy the extracted contents at repository root, preserve live data, and confirm 5.11.24 after redeployment. Configure FRED_API_KEY if not already present, then run Refresh macro snapshots in GitHub Actions. This package does not configure secrets or deploy itself. Live Render/FRED authentication and browser iframe loading are not verified by the automated tests.
