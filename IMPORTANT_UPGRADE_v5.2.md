# IMPORTANT — MarketScope v5.2 Upgrade

This package fixes the blank stock-return problem caused when v5.1 uploaded blank generated data files over the previously populated GitHub snapshot.

## Upgrade the existing GitHub repository

Upload the v5.2 files **on top of the existing repository**. Do not delete these existing generated files first:

- `data/default_universe.csv`
- `data/market_snapshot.csv`
- `data/snapshot_metadata.json`

They are intentionally absent from this ZIP. GitHub will leave them untouched when you upload the v5.2 files, and Render will continue to open with the last saved return percentages immediately.

The ZIP contains only these safe fallbacks:

- `data/default_universe.bootstrap.csv`
- `data/market_snapshot.bootstrap.csv`
- `data/snapshot_metadata.bootstrap.json`

The daily GitHub Action continues to own and refresh the generated files at 6:00 PM `America/New_York` every day.

## Manual Refresh

Manual Refresh now starts from the durable GitHub snapshot before requesting fresh Yahoo history. If Yahoo temporarily throttles Render, MarketScope keeps the last saved stock/ETF returns instead of replacing them with blanks.
