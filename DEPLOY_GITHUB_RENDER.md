# Deploy MarketScope v5.4 to GitHub + Render

Upload all v5.4 files **on top of the existing repository**. Do not delete the generated data files first:

- `data/default_universe.csv`
- `data/market_snapshot.csv`
- `data/snapshot_metadata.json`

The v5.4 ZIP does not contain those generated paths, so your last durable snapshot remains intact during the upgrade.

After committing v5.4, Render can redeploy automatically. To populate the new **3Y Avg**, **1Y Avg**, and buy-signal fields immediately, open GitHub **Actions**, choose **Refresh MarketScope universe and snapshot (v5.4)**, and click **Run workflow**. Otherwise, the workflow runs automatically every day at **6:00 PM America/New_York**.

## Render manual persistence

For manual refreshes to survive Render restarts and appear on every device, set this Render secret environment variable:

`MARKETSCOPE_GITHUB_TOKEN`

Use a fine-grained GitHub token with **Contents: Read and write** permission limited to the MarketScope repository. Do not commit the token to GitHub.

The app continues to start from the last saved snapshot instead of recalculating the universe when the browser opens.
