# MarketScope v5.3 deployment notes

v5.3 raises the automatic Nasdaq stock-universe threshold from >$100M to **strictly >$100B** and removes the unofficial mirror fallback. The automatic stock list now comes only from the direct Nasdaq Stock Screener endpoint.

The app defensively filters older v5.2 generated data on startup, so legacy automatic stocks below $100B disappear immediately after the code upgrade. The next GitHub Action rebuilds `data/default_universe.csv` and `data/market_snapshot.csv` using the new threshold.

Do not delete the existing generated CSV/metadata files before uploading this upgrade. They remain the persistent last-known-good server snapshot until the v5.3 refresh completes.

UI changes: button/pill filters, larger table text/rows, hidden source/timestamp columns, and one Rating update + Snapshot update strip above the table.
