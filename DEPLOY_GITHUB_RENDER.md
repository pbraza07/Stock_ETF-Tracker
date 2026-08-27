# Deploy MarketScope v5.3 to GitHub + Render

## Existing repository upgrade

Upload all v5.3 files on top of your current repository. Do **not** delete these generated files before the upload:

- `data/default_universe.csv`
- `data/market_snapshot.csv`
- `data/snapshot_metadata.json`

The v5.3 ZIP intentionally does not contain those paths, so GitHub leaves the last populated server snapshot intact.

After committing v5.3, Render can redeploy automatically. The app immediately filters legacy automatic stocks below $100B. To rewrite the persistent generated files immediately, open GitHub **Actions**, choose **Refresh MarketScope universe and snapshot (v5.3)**, and run the workflow manually. Otherwise it runs every day at **6:00 PM America/New_York**.

## Render settings

The repository already contains `render.yaml`. The app binds to Render's `$PORT` and starts with Streamlit.

For durable **manual** refresh/add persistence across devices, configure this Render secret environment variable:

`MARKETSCOPE_GITHUB_TOKEN`

Use a fine-grained GitHub token limited to this repository with **Contents: Read and write**. Never commit the token to GitHub.

## What the daily workflow does

1. Pulls the direct Nasdaq Stock Screener.
2. Keeps only stock rows with market cap strictly above **$100B**.
3. Refreshes Nasdaq stock analyst ratings.
4. Adds the requested ETF allowlist.
5. Preserves explicit manual additions.
6. Downloads adjusted historical market data.
7. Calculates return columns.
8. Commits the persistent universe, snapshot, and metadata to GitHub.

All application refresh timestamps are displayed in U.S. Eastern time.
