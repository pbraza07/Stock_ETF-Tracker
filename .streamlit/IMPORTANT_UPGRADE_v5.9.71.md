# MarketScope v5.9.71 — Display Mode Searchable Dropdowns

## Requested change

Under **Market Navigator → Display Mode**, the old free-text search boxes in both Card View and Table View have been replaced with searchable dropdown selectors matching the interaction used in Portfolio Simulator and Stock & ETF Comparison.

## Card View

The new **Search / select stocks & ETFs** control:

- is a searchable `multiselect` dropdown
- supports one or multiple selected instruments
- displays options as `Ticker — Name • Type • Sector`
- can be searched by ticker, company/ETF name, type, or sector
- filters Card View to the exact selected instruments
- shows all currently-filtered Card View instruments when no selection is active

## Table View

Table View now uses the same searchable multiselect behavior. It remains compatible with:

- Sort Table By
- High → Low / Low → High
- click-column interactive sorting
- annual-return columns
- price targets
- investment simulation columns
- yearly-withdrawal columns

## Filter safety

If Quick Filters or other Market Navigator filters remove a stock/ETF that had previously been selected in a Display Mode dropdown, MarketScope automatically removes that stale selection from the widget. This prevents stale Streamlit state from causing invalid choices.

## Independent views

Card View and Table View keep separate selections. Choosing instruments in one view does not unexpectedly modify the other view.

## Existing functionality preserved

No annual/monthly return calculations, price-target logic, ranking data, portfolio simulations, withdrawals, saved simulations, Nasdaq history, or PDF calculations were changed.

The Portfolio PDF contract is bumped to **v29** so rebuilt saved PDFs identify MarketScope v5.9.71.
