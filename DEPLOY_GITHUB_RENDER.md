# Deploy MarketScope v4 to GitHub + Render

## 1. Create / update the GitHub repository

Unzip the package and upload **the files inside the folder**, not the outer ZIP, to the root of your GitHub repository.

Make sure these are visible at repository root:

- `app.py`
- `requirements.txt`
- `render.yaml`
- `.python-version`
- `.github/workflows/update_market_snapshot.yml`
- `data/etf_allowlist.csv`
- `scripts/update_universe.py`
- `scripts/update_snapshot.py`

## 2. Let GitHub build the full universe

A push to `main` starts the workflow automatically unless the push changed only the generated universe/snapshot files.

You can also run it manually:

1. GitHub repository → **Actions**
2. Select **Refresh MarketScope universe and snapshot**
3. Click **Run workflow**
4. Wait for a successful green check

The action:

1. Downloads the current Nasdaq stock-screener universe.
2. Keeps rows with Market Cap > $100,000,000.
3. Merges all requested ETFs from `data/etf_allowlist.csv`.
4. Downloads Yahoo adjusted history in batches.
5. Calculates 10Y Avg, 5Y Avg, 1Y, YTD, 6M, 3M, 1M and 1D.
6. Commits `data/default_universe.csv` and `data/market_snapshot.csv` back to the repository.

The first full snapshot is the heaviest run because it covers thousands of securities. Subsequent app openings do not repeat that work.

## 3. Deploy with Render Blueprint

In Render:

1. **New** → **Blueprint**.
2. Connect the GitHub repository.
3. Render detects `render.yaml`.
4. Apply the Blueprint.

No paid market-data API key is required.

## 4. How daily updates work

GitHub Actions runs at 23:15 UTC Monday–Friday. It refreshes both the market-cap universe and performance snapshot. The commit triggers Render auto-deploy so the next app load uses the new CSV.

## 5. Render Free cold start

The app's own data load is fast because it reads CSV. Render's free web service can still sleep after inactivity; waking the service is separate from MarketScope's market-data processing.

## 6. If the universe says only a few hundred rows

The ZIP includes a bootstrap universe so the project is deployable before internet refresh. Run the GitHub Action once; `data/default_universe.csv` will then expand to the current $100M+ stock universe plus the requested ETFs.
