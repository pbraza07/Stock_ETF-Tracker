# IMPORTANT — MarketScope v5.3 Upgrade

Upload the v5.3 files **on top of the existing GitHub repository**.

Do **not** delete these generated files first:

- `data/default_universe.csv`
- `data/market_snapshot.csv`
- `data/snapshot_metadata.json`

They are intentionally absent from this ZIP so your last successful return snapshot remains available during deployment.

After v5.3 is committed:

1. Render can redeploy the code normally.
2. The app immediately filters legacy automatic stock rows to >$100B.
3. Run the GitHub Action once manually if you want the generated server files rewritten immediately instead of waiting for the normal 6:00 PM Eastern schedule.
4. The scheduled refresh then keeps only direct Nasdaq Stock Screener stocks strictly above $100B, plus the ETF allowlist and explicit manual additions.
