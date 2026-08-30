# MarketScope Return & Market Intelligence Methodology — v5.9.1

## Returns

- 1D / 1M / 3M / 6M / YTD: point-to-point adjusted market returns.
- Ten year-labeled return fields: actual completed calendar-year adjusted returns.
- Calendar-year fields are **not CAGR**.
- Investment simulator compounds the selected number of contiguous completed calendar-year returns and optionally current YTD.

## Live chart

The Open Instrument action renders Yahoo/yfinance intraday data only for the selected symbol. MarketScope requests 1-minute bars for the current day and falls back to 5-minute bars when necessary. The live fragment reruns about every 60 seconds while open. Yahoo/exchange delay can apply.

## Analyst price targets

Stock cards display Yahoo/yfinance analyst **Low / Average / High** target prices when available. The average target is the mean target reported by the source. Missing targets remain blank (`—`). ETFs do not receive fabricated stock-style target ranges.

These targets and all buy/news signals are informational screening data, not guarantees or investment advice.


## Portfolio analytics (v5.9.6)
- 10-year CAGR in the Portfolio Information table is computed only when all 10 completed calendar-year returns are available: the product of the 10 annual return factors is annualized over 10 years.
- Positive years, best year and worst year are based on the available completed calendar-year return columns saved in MarketScope.
- Regular yield is a trailing Yahoo dividend/distribution yield estimate; estimated annual dividend is allocated dollars multiplied by that yield. It is informational, not a forecast, and does not include taxes or reinvestment.


## Combined portfolio PDF metrics (v5.9.7)
- Combined timeframe return = sum of each instrument's saved return multiplied by its normalized portfolio allocation weight.
- A combined timeframe is left unavailable if any positive-weight instrument lacks that saved return, preventing partial-coverage results from being presented as the full portfolio.
- Combined 10Y CAGR compounds the ten combined calendar-year portfolio returns and annualizes the resulting growth over 10 years.
- Combined positive years, worst year and best year are based on the allocation-weighted combined calendar-year returns.
- Combined regular yield is the allocation-weighted saved trailing yield when all selected instruments have a saved yield.
- Combined estimated annual dividend is the sum of the saved per-instrument annual dividend estimates when all are available.


## Stock comparison (v5.9.8)
The comparison workspace does not calculate a new return methodology. It displays the same persisted MarketScope stock fields side by side. Return columns therefore use the existing adjusted-history rules: 1D/1M/3M/6M/YTD are point-to-point adjusted returns and the labeled years are actual completed calendar-year returns. Investment comparison fields use the currently selected MarketScope simulation period and amount.
