# MarketScope v5.11.22 — Reliable macro-data setup

## Why Refresh did not help

v5.11.21 retried public CSV/HTML endpoints and masked the underlying error. If downloads never succeeded, there was no fallback. Its local cache could disappear on Render redeploy. A screenshot alone cannot distinguish a provider HTTP rejection, timeout, or changed markup.

v5.11.22 displays safe connection diagnostics, supports official APIs and restores last-successful snapshots from GitHub. It does not bypass provider restrictions or claim data exist when downloads have failed.

## FRED charts — recommended setup

1. Sign in to FRED and obtain an API key: https://fred.stlouisfed.org/docs/api/api_key.html
2. In Render, open MarketScope → Environment → Add Environment Variable.
3. Name: FRED_API_KEY. Value: your FRED API key. Save and redeploy.
4. In GitHub, open Stock_ETF-Tracker → Settings → Secrets and variables → Actions → New repository secret. Add FRED_API_KEY with the same value.
5. Upload this release, then GitHub → Actions → Refresh macro snapshots → Run workflow.
6. A successful run writes data/macro_snapshots/USPHCI.json and RECPROUSM156N.json. In the app, select Recession Indicators → Refresh recession data.

With FRED_API_KEY present, the app uses the official observations API for the exact requested series. Without it, the legacy public CSV download remains available but can still fail. API credentials and account access must be valid; no key was configured or authenticated live during development.

## Economic calendar — choose a provider

Investing.com remains the default. It does not provide a public data API, according to its support page. The existing public-page collector remains best effort. Repeated refreshes cannot fix a persistent provider block or unsupported HTML layout. GitHub snapshots help only after at least one successful collection; they cannot manufacture unavailable events.

Optional supported API alternative:
1. Obtain Trading Economics API credentials with United States economic-calendar access. Check the provider's plan/access requirements; charges may apply. No purchase is made by this update.
2. Add TRADING_ECONOMICS_API_KEY in Render Environment and GitHub Actions secrets. Use the API credential format supplied by Trading Economics.
3. Redeploy, then select Trading Economics API in the dashboard's Calendar data source field.
4. Run Refresh macro snapshots in GitHub Actions. The workflow collects the optional API source when credentials exist.

The selected API source is labeled Trading Economics, never Investing.com. Importance 3 is its own high-impact classification. Both sources filter United States only and display Eastern announcement times. Numeric units are preserved; API results are neutral-colored unless the provider explicitly supplies a better/worse assessment.

Documentation: https://docs.tradingeconomics.com/economic_calendar/country/
Investing.com API policy: https://pro.investing-support.com/hc/en-us/articles/4408847632017-Do-You-Offer-API-Access-at-Investing-com

## Snapshot workflow

- Runs every six hours and manually; GitHub schedules can be delayed.
- Uses the built-in GitHub Actions token with contents:write, not the ChatGPT connection.
- Writes only successful downloads. A provider failure leaves the last good snapshot untouched and makes the workflow failure visible after saving successes.
- Snapshot commits use [skip render]; the app can retrieve them directly without redeployment.
- The raw GitHub snapshot fallback assumes the current repository is publicly readable. Private repositories require an additional authenticated delivery design; do not make a private repository public just to enable this fallback.
- Source timestamps stay unchanged on fallback. The app labels unsuccessful refreshes as stale, even if a useful snapshot is displayed.
- Snapshots are excluded from the upgrade ZIP to preserve deployed data. Upload release contents without deleting existing data/macro_snapshots.

## Verification after setup

Confirm the workflow succeeds for each required provider, inspect the corresponding JSON file and retrieval date, then refresh the app. If a provider still fails, open Connection details and use the reported error. Never share API keys in chat or screenshots.
