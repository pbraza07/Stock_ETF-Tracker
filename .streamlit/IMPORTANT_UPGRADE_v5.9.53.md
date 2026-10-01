# MarketScope v5.9.53 - Verified 25-Year Historical Backfill

This release fixes the blank 21Y-25Y annual-return columns seen after the v5.9.50 UI expansion.

## Root cause

The interface had been expanded to 25 completed calendar years, but the durable `data/market_snapshot.csv` still contained annual columns only through 2006. Therefore 2005, 2004, 2003, 2002 and 2001 displayed as empty even though the UI knew those horizons existed.

## Fixes

- Scheduled refresh calculates 25 completed calendar years from Yahoo/yfinance `period=max` adjusted history.
- A new CI validation step refuses to accept a refreshed snapshot unless all columns 2025 through 2001 exist and each of 2005-2001 has genuine data for at least 10 instruments.
- App startup compares local, GitHub and bootstrap snapshots and selects the source with the strongest real 25-year annual coverage before considering price population.
- A stale 20-year local snapshot can no longer override a newer 25-year GitHub snapshot.
- If the oldest five years are still absent, MarketScope shows a **Repair 25Y annual history now** action. It downloads max adjusted history in batches, writes only genuine calculated returns, and persists the repaired snapshot locally/GitHub when configured.
- Snapshot metadata now records annual-history year count, oldest annual year with data, and row counts per year.
- PDF layout advances to v14 so saved Portfolio PDFs rebuild after the verified 25-year backfill.

## App-wide behavior

The verified 25-year data flows through Market Navigator Card View and Table View, Investment Simulator, Portfolio Simulator, Stock & ETF Comparison, Sector Performance, Worst Year calculations, 1Y-25Y horizon selectors, common-history logic, annual withdrawal simulations, year charts, and Portfolio PDFs.

No pre-inception or pre-IPO returns are fabricated. A ticker with no genuine history for an older year remains unavailable for that specific year.
