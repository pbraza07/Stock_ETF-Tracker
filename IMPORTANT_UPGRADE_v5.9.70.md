# MarketScope v5.9.70 — Durable 6-Month Change History

## New Market Navigator button

A new button appears beside **Refresh Nasdaq Universe Now**:

**🕘 6-Month Change History**

The button opens a historical table containing every recorded change from the latest six months.

## Changes recorded

MarketScope records three event types:

1. **Stock Added**
   - symbol crossed into the tracked Nasdaq >$100B universe

2. **Stock Removed**
   - symbol left the tracked Nasdaq >$100B universe

3. **Analyst Rating**
   - Nasdaq consensus changed from one rating bucket to another

Each event stores:

- ET timestamp
- event type
- symbol
- company name when available
- previous state/rating
- new state/rating
- source

## History is never pruned

The durable file is:

`data/universe_change_history.json`

This file is append-only. MarketScope does **not** delete records after six months.

The user interface applies a six-month filter only when displaying the table. Older history remains in the file for future historical analysis.

## First-upgrade migration

Before v5.9.70, MarketScope only retained the latest refresh changes inside `universe_metadata.json`.

On the first v5.9.70 universe refresh, the updater automatically converts those immediately prior metadata changes into historical events before writing the new refresh. This preserves the latest pre-upgrade event when possible.

History from older refreshes that was never persisted by earlier versions cannot be reconstructed or invented.

## Scheduled refresh

The daily GitHub workflow now persists these three files immediately after the Nasdaq universe refresh:

- `data/default_universe.csv`
- `data/universe_metadata.json`
- `data/universe_change_history.json`

A later Yahoo/history/ranking failure therefore cannot erase or prevent persistence of the newly recorded history.

## Manual refresh

**Refresh Nasdaq Universe Now** now starts from the durable GitHub history before running the updater and persists the updated history back to GitHub with the same existing Contents read/write token.

This prevents ephemeral Render storage from losing older history.

## 6-month view

When opened, the history panel shows:

- Total changes
- Stocks added
- Stocks removed
- Rating changes

and a detailed sortable table:

- Date / Time (ET)
- Change Type
- Symbol
- Name
- Previous
- New
- Source

## Existing functionality

No market-return, price-target, portfolio, withdrawal, ranking, or PDF calculations are changed.

The v5.9.69 Saved Simulation inline-withdrawal card remains intact.

The Portfolio PDF contract is bumped to **v28** only so rebuilt PDFs identify the current MarketScope release.
