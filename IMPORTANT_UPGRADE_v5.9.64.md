# MarketScope v5.9.64 - Price Target Restore

This release repairs the analyst price-target path across the entire app and saved Portfolio PDFs.

## Root cause

MarketScope already had the PDF placeholders for `LOW / AVG-CONS / HIGH`, but recent releases only performed the lazy Yahoo target fallback inside the visible Market Navigator card rows. The main `market` dataframe used by Portfolio Simulator saves and saved-PDF rebuilds could therefore still contain blank target fields. As a result, the PDF layout rendered correctly but showed `LOW - AVG/CONS - HIGH -`.

## App-wide target hydration

v5.9.64 adds one shared `_hydrate_price_targets()` path. Durable snapshot values are preferred. When any of the three target fields is missing for a stock, the app asks the shared cached Yahoo/yfinance target loader and fills the available range.

The same helper is now used by:

- Market Navigator Card View
- Market Table View
- Instrument Full Details
- Stock & ETF Comparison cards
- Comparison Table
- Comparison Full Details
- Portfolio Simulator save records
- Saved Portfolio PDF rebuild enrichment

ETFs remain blank when stock-style analyst target consensus is not published.

## PDF repair

The PDF layout contract is bumped to v23. Opening or rebuilding an older saved simulation forces current enrichment before PDF generation, including current price, analyst rating, Low target, Average/Consensus target, and High target.

The Portfolio Instrument Snapshot continues to display:

`LOW $...   AVG/CONS $...   HIGH $...`

and no longer depends on the user having visited a Market Navigator card first.

## Provider reliability

Yahoo target requests now use lower concurrency and retry missing symbols individually once. This reduces transient target gaps on Render when Yahoo throttles concurrent quote-summary metadata calls.

The normal scheduled snapshot refresh continues to persist the three target fields and now uses the same lower-concurrency resilient batch method.

## Bootstrap schema

`market_snapshot.bootstrap.csv` now includes the four target columns so a first-start/fallback snapshot has the same schema as the durable production snapshot.
