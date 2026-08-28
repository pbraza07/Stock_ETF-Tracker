# MarketScope v5.6

MarketScope is a responsive stock/ETF performance navigator designed for GitHub + Render.

## v5.6 highlights
- Futuristic card/button interface replaces the primary spreadsheet table.
- Tap **Open SYMBOL** to inspect a stock or ETF.
- Responsive instrument cards show symbol, name, price, 1D, YTD, 1Y Avg, analyst rating and buy-signal state.
- Full performance matrix after opening a card:
  **1D → 1M → 3M → 6M → YTD → 1Y Avg → 2Y Avg → 3Y Avg → 4Y Avg → 5Y Avg → 6Y Avg → 7Y Avg → 8Y Avg → 9Y Avg → 10Y Avg**.
- 1Y–10Y Avg fields are CAGR from adjusted daily history.
- Clickable filters, sectors, analyst ratings and buy-signal filters remain available.
- Automatic universe remains Nasdaq Stock Screener stocks strictly above $100B plus the ETF allowlist and manually persisted symbols.
- Daily refresh remains 6:00 PM U.S. Eastern.
- Manual refresh retains visible progress count and percentage.
- Durable GitHub snapshot persistence remains unchanged.

## Deploy
Upload this package over the existing repository. Do not delete populated `data/default_universe.csv`, `data/market_snapshot.csv`, or `data/snapshot_metadata.json` before the upgrade. Then run the MarketScope GitHub Action once to populate the new annualized horizons.

See `IMPORTANT_UPGRADE_v5.6.md` and `DEPLOY_GITHUB_RENDER.md`.


## v5.6 card-data update
- Every stock/ETF card now shows all 15 requested return horizons: 1D, 1M, 3M, 6M, YTD, and annualized 1Y through 10Y averages.
- Every one of those horizons can be selected as a card-sort button, along with Analyst Rating and Market Cap.
- Sort direction can be switched between High → Low and Low → High.
- The ETF universe is now locked to the 213 ETFs present in the supplied CSV universe files. `data/etf_allowlist.csv` is rebuilt to the same 213 symbols so scheduled refreshes do not expand back to the older 229-symbol list.
