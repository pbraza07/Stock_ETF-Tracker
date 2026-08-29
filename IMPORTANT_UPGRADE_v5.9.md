# IMPORTANT — Upgrading to MarketScope v5.9

Upload v5.9 **on top of the existing repository**. Do not delete the durable generated snapshot files before the upload.

After deployment, run **GitHub → Actions → Refresh MarketScope universe and snapshot (v5.9) → Run workflow** once. This populates the new stock price-target fields in the durable snapshot.

If you open the app before that Action completes, v5.9 can lazily fetch target data only for the visible stock cards, so the dashboard remains upgrade-safe.

The 213-ETF CSV universe is unchanged.
