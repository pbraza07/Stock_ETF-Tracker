# MarketScope v3 — GitHub + Render deployment

## Why v3 is faster

v2 downloaded the maximum available daily history for the entire watchlist during the first Streamlit run. On a free Render service that meant the user waited while the server contacted Yahoo Finance, and a Yahoo rate-limit could leave the table empty.

v3 uses a **snapshot-first architecture**:

1. `data/market_snapshot.csv` contains all expensive performance calculations.
2. The Streamlit app reads that local CSV immediately at startup.
3. Render's build command populates the snapshot before the app starts.
4. GitHub Actions refreshes the snapshot at 6:17 PM America/New_York, Monday-Friday.
5. The Live Refresh button requests only current intraday prices.
6. A detail chart is requested for one ticker only when you ask for it.

This does not eliminate Render Free's platform cold start after an idle period, but it removes the second wait caused by downloading decades of Yahoo history after Streamlit is already awake.

## Deploy

1. Upload every file in this ZIP to the root of a GitHub repository.
2. Commit and push.
3. In Render, create a Blueprint from the repository.
4. Render reads `render.yaml`, installs packages, and runs `python scripts/update_snapshot.py` during the build.
5. After deployment, open the Render URL.

## Run the daily updater manually the first time

In GitHub:

1. Open **Actions**.
2. Select **Update market snapshot**.
3. Select **Run workflow**.
4. Wait for the workflow to finish.

If it obtains fresher data, it commits `data/market_snapshot.csv` automatically. A connected Render service then redeploys the new snapshot.

## Important free-tier behavior

Render Free web services can spin down after inactivity. A cold start is controlled by Render, not by the Python code. Once the Streamlit process is awake, v3 displays the saved snapshot without waiting for a full Yahoo historical download.

## Yahoo rate limiting

Yahoo can temporarily throttle requests from cloud-hosting IPs. v3 is designed to remain useful during that event: it keeps displaying the last successful daily snapshot and only the optional live refresh/chart may be unavailable temporarily.
