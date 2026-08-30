# MarketScope v5.9.25 — Comparison Charts, Navigator Logos & Stock Sector Performance

Built directly from v5.9.24.

## Changes
- Fixed Comparison Card 2Y chart loading by fetching chart history for the actual selected comparison symbols instead of reusing the current Market Navigator page cache.
- Added Yahoo/company instrument logos to Market Navigator Card View using the same cached logo provider/fallback used by Comparison.
- Comparison cards now share the same header renderer as Market Navigator, including logo and 2Y chart.
- Added top-level **Sector Performance** tab for stocks only.
- Sector cards include every MarketScope timeframe and aggregate all tracked stocks in each sector.
- Sector aggregation supports Equal Weight (default) and Market-Cap Weighted modes.
- Sector cards add member-stock count, combined market cap, positive-return breadth, and Buy/Strong Buy analyst-rating breadth.
- Added sortable sector performance table beneath the cards.
