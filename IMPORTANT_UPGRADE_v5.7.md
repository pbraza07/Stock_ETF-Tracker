# IMPORTANT — v5.7 Upgrade

v5.7 changes the visible long-horizon methodology from CAGR to actual completed calendar-year returns.

After committing the files, run **GitHub Actions → Refresh MarketScope universe and snapshot (v5.7) → Run workflow** once. This refresh uses maximum available adjusted history so MarketScope can calculate ten full calendar years correctly.

Do not manually translate the old `1Y Avg` through `10Y Avg` columns into year labels. They are different statistics. v5.7 intentionally leaves annual-year cells blank until real history is processed.

The 213-ETF CSV files are preserved.
