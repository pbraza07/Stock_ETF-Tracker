# Deploy MarketScope v5.11.2 to GitHub + Render

## v5.11.2 - Permanent Favorite Picks Change Trail

1. Preserve v5.11.1 as the rollback package.
2. Upload the extracted v5.11.2 contents directly to the GitHub repository root. Confirm `requirements.txt`, `app.py`, `render.yaml`, and `Procfile` remain at that root, and keep Render's **Root Directory** blank.
3. Preserve the live `data/favorite_picks_history.json` file. The release intentionally contains only `data/favorite_picks_history.bootstrap.json` so an upgrade cannot erase earlier Pick Fav runs or first-detected dates.
4. Continue preserving `data/universe_change_history.json`, `data/saved_portfolio_simulations.json`, `data/generated_pdfs/`, and `static/generated_pdfs/`.
5. Keep `MARKETSCOPE_GITHUB_REPO`, `MARKETSCOPE_GITHUB_BRANCH`, and `MARKETSCOPE_GITHUB_TOKEN` unchanged. The token needs repository **Contents: Read and write** permission for manual Pick Fav runs to persist across Render restarts and devices.
6. Commit and push to `main`. The workflow will update Favorite Picks after the verified market snapshot and commit `data/favorite_picks_history.json` even if nobody opens the app.
7. After Render is healthy, select **Pick Fav** twice. The first run should establish initial events; the unchanged second run should add a run-audit record without duplicating change events.
8. Open Market Navigator → **Pick Fav Change Trail** and verify replacement rows show Dropped Pick, New Pick, and the immutable First Detected timestamp.
9. Open the existing six-month stock/analyst history and its all-time archive. Confirm earlier addition/removal/rating dates remain intact.

No new dependencies or environment-variable names are required. The existing historical simulators and Future Projection calculation engine are unchanged.

# Deploy MarketScope v5.11.1 to GitHub + Render

## v5.11.1 - Favorite Picks

1. Preserve v5.11.0 as the rollback package.
2. Extract the v5.11.1 repository-root ZIP. Upload the ZIP's **contents** directly to the root of `pbraza07/Stock_ETF-Tracker`; do not place the application inside a `data/` folder or an extra enclosing release folder.
3. Confirm `requirements.txt`, `app.py`, `render.yaml`, and `Procfile` are visible at the GitHub repository root. This prevents Render's `Could not open requirements file` build failure.
4. Preserve `data/saved_portfolio_simulations.json`, `data/generated_pdfs/`, and `static/generated_pdfs/` from the live repository.
5. In Render, leave **Root Directory** blank for this flattened package. If the repository is intentionally still nested under `data/`, set Root Directory to `data` only until the repository is corrected.
6. Keep the existing build command `python -m pip install --upgrade pip && pip install -r requirements.txt` and the existing Streamlit start command. No new environment variables or dependencies are required.
7. Commit and push to `main`. After Render is healthy, open **Favorite Picks**, select **Pick Fav**, and verify the Top 2 table, regime panel, explanations, data dates, warnings, and CSV download.
8. Run the existing Future Projection and Portfolio Simulator smoke checks to confirm this release did not change their calculations.

The Favorite Picks calculation may retrieve supplemental live/recent data through the same providers as Future Projection. If a supplemental source is unavailable, the table uses labeled historical assumptions and continues rather than failing the whole app.

# Deploy MarketScope v5.11.0 to GitHub + Render

## v5.11.0 - Live Adaptive Future Projection

1. Preserve the existing v5.10.1 package as the rollback copy.
2. Extract the v5.11.0 ZIP and upload its contents over the existing `pbraza07/Stock_ETF-Tracker` repository. Do not delete live data files that are absent from the release.
3. Preserve `data/saved_portfolio_simulations.json`, `data/generated_pdfs/`, and `static/generated_pdfs/`.
4. Commit and push to `main`; the existing `render.yaml`, `Procfile`, and Streamlit health endpoint remain valid.
5. Keep `MARKETSCOPE_GITHUB_REPO`, `MARKETSCOPE_GITHUB_BRANCH`, and `MARKETSCOPE_GITHUB_TOKEN` unchanged. There are no new required environment variables.
6. After Render is healthy, open Future Projection, select at least one holding, confirm the start year, run an Advanced projection, and verify the market-state dashboard, P10/P25/P50/P75/P90 charts, tables, and downloads.
7. Temporarily block a supplemental source or run offline and verify the projection shows a labeled cached or historical fallback rather than an unresolved loading state.

The live adaptive cache is local and excluded from Git. It is rebuilt automatically and never replaces the durable historical snapshot. Existing historical portfolio simulators and ranking files are not recalculated by changing Future Projection inputs.

# Deploy MarketScope v5.10.1 to GitHub + Render

## v5.10.1 — Empty Future Projection portfolio fix

Upload the v5.10.1 files over the existing repository and push to `main`. No data migration, dependency change, or environment-variable change is required. The fix affects only pre-run Future Projection validation and does not alter projection or historical simulator calculations.

## v5.10.0 — Future Projection

1. Extract the v5.10.0 ZIP and upload its contents over the current repository; do not delete the repository first.
2. Preserve `data/saved_portfolio_simulations.json`, `data/generated_pdfs/`, and `static/generated_pdfs/` if they exist in the live repository. They are intentionally absent from the release ZIP.
3. Commit and push to `main`. Render installs `plotly` and `openpyxl` from `requirements.txt` and auto-deploys using the existing `render.yaml` start command.
4. Keep the existing `MARKETSCOPE_GITHUB_REPO`, `MARKETSCOPE_GITHUB_BRANCH`, and optional `MARKETSCOPE_GITHUB_TOKEN` settings. No new environment variables or data migration are required.
5. After Render reports healthy, open **Future Projection**, load four holdings, run an Advanced projection, and verify the chart and Excel/CSV/PDF downloads.
6. Run the existing **Refresh MarketScope universe, snapshot and actual monthly rankings (v5.10.0)** GitHub Action once only if the historical snapshot or actual-monthly files are stale.

The Future Projection tab reads the existing MarketScope stock/ETF universe and historical files. Deploying it does not recalculate or overwrite existing historical simulator results or Top-50/Top-100/Top-250 rankings.

## Earlier deployment history

The original v5.8.1 instructions below are retained for upgrade history.

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

## v5.9.18 universe status metadata

The scheduled 6:00 PM ET GitHub Action now also commits `data/universe_metadata.json`. This file records the latest Nasdaq >$100B screening timestamp plus the symbols added and removed from the automatic stock universe on that refresh. Run the workflow once after upgrading so the new status strip is populated.


## v5.9.40 — preserve saved Portfolio PDFs on every upgrade

Treat these GitHub paths as protected live user data and **leave them in place** when uploading a new MarketScope release:

- `data/saved_portfolio_simulations.json`
- `data/generated_pdfs/`

The release package does not ship those live paths. Upload/commit the release files **on top of** the existing repository; do not delete repository files merely because they are absent from the ZIP.

Keep the Render environment variable `MARKETSCOPE_GITHUB_TOKEN` unchanged. It needs GitHub Contents read/write permission. With that token, saved simulation records and PDFs survive Render restarts and future code deployments, and missing local PDF copies are restored from GitHub automatically.

Optional: for a second durable copy on a paid Render persistent disk, mount a disk and set `MARKETSCOPE_PDF_PERSIST_DIR` to a directory on that disk.
