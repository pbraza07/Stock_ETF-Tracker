# IMPORTANT — MarketScope v5.4 Upgrade

Upload v5.4 **on top of the current repository**.

Do not delete or replace these generated files before the upload:

- `data/default_universe.csv`
- `data/market_snapshot.csv`
- `data/snapshot_metadata.json`

After the code is committed, run the v5.4 GitHub Action once if you want the new 3Y Avg and buy-signal fields populated immediately. The normal scheduled refresh is 6:00 PM America/New_York every day.

Older snapshots are migrated safely: the previous `1Y` value is used temporarily as `1Y Avg`, and all new signal fields default to inactive until refreshed.
