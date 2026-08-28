# Deploy MarketScope v5.8.1 to GitHub + Render

Upload the v5.8.1 files **on top of the existing repository** and commit to `main`.

## Preserve durable data

Keep these files unless you intentionally want to rebuild them:

- `data/default_universe.csv`
- `data/market_snapshot.csv`
- `data/snapshot_metadata.json`

The package still includes the 213-ETF CSV universe and compatible snapshot files. GitHub remains the durable source of truth.

## After committing v5.8.1

1. Open **GitHub → Actions**.
2. Choose **Refresh MarketScope universe and snapshot (v5.8.1)**.
3. Run the workflow once if the annual-return snapshot is stale.
4. Let Render auto-deploy the new commit.
5. Test a card's **News** button, the **Investment years** control, **Total Profit ($)** sorting, and multiple **Chart year** selections.

The scheduled refresh remains every calendar day at **6:00 PM America/New_York**.

News is fetched on demand when a user clicks News; it is not bulk-downloaded for every instrument during the daily job.


## v5.9 post-upgrade step

After uploading v5.9, run the **Refresh MarketScope universe and snapshot (v5.9)** GitHub Action once. This backfills Price Target Low / Average / High into the durable snapshot. The app can still lazily fetch targets for visible stock cards before that run finishes.


## v5.9.2
Upload this release over the existing repository. No market snapshot reset is required. ETF holdings are retrieved on demand and do not need a scheduled refresh. Bottom card pagination is UI-only.
