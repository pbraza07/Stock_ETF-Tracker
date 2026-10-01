# MarketScope v5.9.66 — End-to-End Analyst Price Target Fix

This release fixes the remaining blank Low / Average-Consensus / High analyst targets in Market Table and Portfolio PDF page 1.

## Root causes fixed

1. `YahooFinanceProvider.get_price_targets()` previously wrapped Ticker creation and `analyst_price_targets` access inside one `try`. If the analyst-target property threw once, the code set the ticker object to `None`, which prevented the fallback `get_info()` target fields from running.

2. Snapshot selection ranked candidates by annual-history coverage and price coverage, but not analyst-target coverage. A stale local or bootstrap snapshot with blank targets could therefore beat an otherwise equivalent GitHub snapshot that already contained valid target values.

3. A cached empty Yahoo target result could leave Table View and PDF enrichment blank until cache expiry.

## v5.9.66 target resolution

For stocks, target resolution now uses:

1. durable saved snapshot values
2. current `yfinance.Ticker.get_analyst_price_targets()`
3. `Ticker.analyst_price_targets`
4. `Ticker.get_info()` fields:
   - targetLowPrice
   - targetMeanPrice
   - targetHighPrice
   - targetMedianPrice
5. direct uncached per-symbol retry if a cached batch result is empty or incomplete

A failure in one Yahoo/yfinance target path no longer disables the remaining fallback paths.

Existing valid target values are preserved when Yahoo temporarily returns only part of the range.

## Scheduled snapshot target completion

After the heavy history refresh finishes, `update_snapshot.py` now performs a separate low-concurrency target-completion pass only for stock rows that still lack one or more of Low / Average / High.

The durable snapshot now records:
- Price Target Low
- Price Target Average
- Price Target High
- Price Target Updated ET
- Price Target Source
- count of complete stock target rows
- count of populated target cells

## Snapshot selection

When annual-history quality is equal, MarketScope now prefers the candidate with stronger analyst-target coverage before comparing populated current prices.

If all quality measures tie, GitHub is preferred over stale local/bootstrap data.

## Market Table

Low / Average / High targets now sit directly beside Price and Market Cap instead of being buried farther to the right.

Table View also shows:
- Target Source
- Target Updated ET

## PDF page 1

Saved and rebuilt Portfolio PDFs use the same shared target hydrator as Market Table.

Old saved simulations are forced through PDF layout **v25**, so page 1 is rebuilt using current Low / Average-Consensus / High values when Yahoo publishes them.

The PDF still displays `-` for a security when no stock-style analyst consensus is genuinely available.

## No changes to return or withdrawal math

This release changes analyst-target retrieval, persistence and display only. Portfolio performance, annual returns, monthly returns, rebalancing and withdrawal calculations are unchanged.
