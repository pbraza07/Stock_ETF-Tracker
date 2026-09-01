# IMPORTANT UPGRADE — MarketScope v5.9.32

## Portfolio common-start behavior
MarketScope no longer removes 1Y–20Y choices when a newer stock or ETF is selected. The requested horizon remains selectable. For completed-year simulations, MarketScope identifies the calendar years for which every selected instrument has a valid saved return and uses up to the requested number of newest common years. This prevents pre-IPO/pre-inception simulation errors without fabricating history.

## Sector Performance drill-down
The previous separate View top performers control is removed. TOTAL STOCKS is the clickable drill-down. It opens an in-screen popover with all stocks in the sector. A clickable timeframe selector (1D, 1M, 3M, 6M, YTD, 1Y–20Y) controls ranking and recalculates Total Profit ($) and Total Profit (%) using a user-adjustable investment basis.

No new environment variables are required.
