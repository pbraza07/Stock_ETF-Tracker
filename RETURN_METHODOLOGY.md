# MarketScope Return Methodology

## Important terminology: NAV vs. total return

A **stock does not have NAV (Net Asset Value)**. NAV is a fund concept. An exchange-traded fund has a NAV calculated from the value of the fund's underlying assets, while its exchange-traded market price can trade at a premium or discount to NAV.

For that reason MarketScope does **not** label stock returns as NAV returns, and it does not silently label ETF market-price history as NAV history.

### What the performance columns use

The scalable free-data implementation uses Yahoo Finance history through `yfinance` with `auto_adjust=True` for:

- 10Y Avg — annualized CAGR
- 5Y Avg — annualized CAGR
- 1Y — cumulative adjusted total return
- YTD — cumulative adjusted total return
- 6M — cumulative adjusted total return
- 3M — cumulative adjusted total return
- 1M — cumulative adjusted total return
- 1D — adjusted daily return

The adjusted series is intended to account for corporate actions/distributions reflected by Yahoo's adjusted history. The app explicitly labels the basis:

- Stock: **Adjusted total return**
- ETF: **Adjusted market total return**

### ETF NAV

For ETFs, MarketScope can display the **current NAV** when Yahoo exposes `navPrice`, plus market-price premium/discount to current NAV. This is separate from the historical performance columns.

A true historical ETF NAV-return implementation for every requested ETF would require historical NAV observations from each fund sponsor/issuer (State Street, iShares, Vanguard, Schwab, Invesco, WisdomTree, Avantis, Dimensional, JPMorgan, First Trust, etc.). Those issuer feeds are not standardized into one universally available free Yahoo historical-NAV series. If a strict NAV-only mode is added later, missing issuer NAV history should be shown as `N/A`, not replaced with market-price history.

## Horizon rules

- 10Y Avg / 5Y Avg require near-full horizon coverage and are annualized using actual elapsed time.
- 1Y / 6M / 3M / 1M use the nearest valid trading observation around the calendar anchor.
- YTD compares with the final adjusted close before January 1, or the first valid trading observation of the year when necessary.
- 1D uses the latest adjusted daily close against the prior trading close in the daily snapshot.
- Since Inception is intentionally not fabricated from the bounded 10-year bulk download. Selecting **Load full metrics** for one symbol downloads MAX history and calculates it accurately for that symbol.
