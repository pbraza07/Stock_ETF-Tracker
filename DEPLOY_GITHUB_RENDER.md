# Deploy MarketScope v5.7 to GitHub + Render

Upload the v5.7 files **on top of the existing repository**.

Do not delete these generated live-data files first:

- `data/default_universe.csv`
- `data/market_snapshot.csv`
- `data/snapshot_metadata.json`

The v5.7 ZIP intentionally does not include `data/market_snapshot.csv` or `data/snapshot_metadata.json`, so your last durable live snapshot is not overwritten by the upgrade.

## Required first refresh

After committing v5.7:

1. Open **GitHub → Actions**.
2. Choose **Refresh MarketScope universe and snapshot (v5.7)**.
3. Click **Run workflow**.
4. Wait for the workflow to complete successfully.
5. Render can then auto-deploy the refreshed commit.

This first refresh is important because the old CAGR columns are not equivalent to actual calendar-year returns. v5.7 downloads maximum available adjusted history and calculates the ten completed annual returns from real year-end prices.

The normal schedule remains **6:00 PM America/New_York every day**.

## Render manual persistence

For manual refreshes to survive Render restarts and appear on every device, set the Render secret environment variable:

`MARKETSCOPE_GITHUB_TOKEN`

Use a fine-grained GitHub token with **Contents: Read and write** permission limited to the MarketScope repository. Do not commit the token to GitHub.
