# Return Methodology

MarketScope does not label stock returns as NAV returns because stocks do not have NAV.

## Stocks

Performance columns use Yahoo/yfinance adjusted daily market-price history designed to reflect splits and distributions.

## ETFs

Performance columns currently use adjusted **market total return**. Current ETF NAV is shown separately when available. MarketScope does not silently relabel market-price returns as NAV returns.

## Columns

- `10Y Avg`: annualized CAGR over approximately 10 years when sufficient history exists.
- `5Y Avg`: annualized CAGR over approximately 5 years when sufficient history exists.
- `1Y`: point-to-point adjusted total return.
- `YTD`: adjusted total return from prior year-end.
- `6M`, `3M`, `1M`: point-to-point adjusted total return.
- `1D`: latest trading-day adjusted return or live-price overlay versus the appropriate prior close.
- `Since Inception`: only populated when full-history data has actually been calculated; bounded 10-year refreshes are not mislabeled as inception history.
