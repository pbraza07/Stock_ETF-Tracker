# Deploy MarketScope v5 to GitHub + Render

## 1. Upload to GitHub

Unzip this package and upload **all files inside the folder** to the root of your repository. Your repository should include `app.py`, `render.yaml`, `requirements.txt`, `.github/workflows/update_market_snapshot.yml`, `scripts/`, `providers/`, and `data/`.

The supplied Render configuration assumes the repository is:

`pbraza07/Stock_ETF-Tracker`

If you use a different repository, change `MARKETSCOPE_GITHUB_REPO` in `render.yaml`.

## 2. Run the first full data refresh

In GitHub:

1. Open **Actions**.
2. Select **Refresh MarketScope universe and snapshot**.
3. Click **Run workflow**.
4. Wait for the workflow to finish successfully.

The workflow rebuilds the current Nasdaq >$100M stock universe, adds the 229 ETF allowlist, refreshes Nasdaq analyst ratings, downloads adjusted market history, calculates the performance columns, and commits the resulting persistent CSV/metadata files.

The scheduled workflow automatically runs at **6:00 PM America/New_York every calendar day**.

## 3. Deploy to Render

Create or update the Render Blueprint from the GitHub repository. `render.yaml` contains the build/start commands.

Build command:

`python -m pip install --upgrade pip && pip install -r requirements.txt`

Start command:

`streamlit run app.py --server.address=0.0.0.0 --server.port=$PORT --server.headless=true --browser.gatherUsageStats=false`

## 4. Enable permanent manual-refresh saving

Scheduled refreshes are automatically committed by GitHub Actions. To also make **manual refreshes and manually added symbols permanent across Render restarts and available from every device**, create a fine-grained GitHub token with access only to this repository and **Contents: Read and write** permission.

In Render, set the secret environment variable:

`MARKETSCOPE_GITHUB_TOKEN`

Do not place the token in the repository or source code.

The package also sets:

- `MARKETSCOPE_GITHUB_REPO=pbraza07/Stock_ETF-Tracker`
- `MARKETSCOPE_GITHUB_BRANCH=main`

## 5. How persistence works

- The app opens from the last committed `data/market_snapshot.csv`, so the table appears without doing thousands of live requests first.
- The 6:00 PM ET GitHub Action updates and commits the snapshot each day.
- Render auto-deploys the new committed snapshot.
- A manual refresh first writes the new snapshot to the current Render process immediately and, when `MARKETSCOPE_GITHUB_TOKEN` is configured, commits it to GitHub for durable cross-device persistence.
