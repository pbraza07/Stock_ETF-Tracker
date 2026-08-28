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
