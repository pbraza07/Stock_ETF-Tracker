
## v5.9.18 deployment note

After uploading this release, run the GitHub Action **Refresh MarketScope universe and snapshot** once. The first successful run records the Nasdaq >$100B universe refresh timestamp and the stocks added/removed versus the prior screened universe. Card and Table views start at **1D, high to low**, and the Portfolio Split Simulator starts at **$100,000**.

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

## v5.9.4 — Card / Table tabs
Upload the release over the current repository and let Render redeploy. No snapshot reset is required. Table View reads the same persisted snapshot as Card View.

## v5.9.5 saved simulations

The app now needs `reportlab` (already included in `requirements.txt`) to render saved Portfolio Split Simulator PDFs. Keep `MARKETSCOPE_GITHUB_TOKEN` configured with Contents read/write permission if you want the Saved Simulations library to remain available across Render restarts and devices.

Do not add an empty `data/saved_portfolio_simulations.json` to an upgrade upload. The live file is created and maintained by the running app; the package contains only `data/saved_portfolio_simulations.bootstrap.json`.


### v5.9.7 PDF verification
Save or re-download a Portfolio Split simulation and verify page 1 is landscape and shows both combined tables with readable text: 10Y CAGR / Pos Years / Worst / Best / Reg. Yield / Est. Annual Div., plus 1D through 2006 combined timeframe performance.


### v5.9.8 Stock Comparison
Upload the v5.9.8 files over the existing repository and allow Render to redeploy. No market snapshot schema migration or forced data refresh is required for the comparison feature. Stock comparison uses the existing persisted MarketScope rows.
