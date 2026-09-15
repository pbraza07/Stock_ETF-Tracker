# MarketScope v5.9.22 — PDF First-Page Market Data + Comparison Logos

Built from v5.9.21.

## Changes
- Every newly generated Portfolio Split Simulator PDF puts the required instrument market-data snapshot on page 1: name, sector, analyst rating, current price, low target, average/consensus target, and high target.
- Previously saved simulations are upgraded on first open from the Saved / Manage library. The PDF is rebuilt with the current MarketScope snapshot values and persisted back to the configured server/GitHub PDF store.
- Stock & ETF Comparison fetches instrument logos only for selected symbols, using Yahoo/yfinance metadata first and a company-website favicon fallback when Yahoo does not expose a direct logo URL.
- Comparison Cards now show the logo beside ticker/name.
- Comparison Table now includes a Logo image column.
- Ticker initials remain the visual fallback if no logo can be retrieved.
- Existing Share PDF and Back to MarketScope mobile-viewer controls remain unchanged.
