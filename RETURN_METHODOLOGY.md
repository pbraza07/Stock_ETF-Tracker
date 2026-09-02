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


## v5.9.46 Monthly withdrawal methodology

When **Monthly withdrawal** is enabled, MarketScope uses actual adjusted month-end market prices. For each month, return equals the final adjusted close of the current month divided by the final adjusted close of the prior month minus 1. January uses the prior December month-end adjusted close as its base.

Return is applied first and the selected cash withdrawal is then taken at month-end. **Rebalanced Monthly** restores the target weights after each withdrawal; **Not Rebalanced Monthly** carries the drifted holdings forward. Annual return fields are not divided, averaged, rooted, or otherwise transformed into synthetic monthly values.

The scheduled GitHub refresh persists the latest ten completed years of actual monthly returns to `data/monthly_returns_10y.csv` and rebuilds the two Top 100 monthly withdrawal rankings from that actual monthly series.

## v5.9.56 independent verification

For each instrument and each available completed calendar year from 2025 through 2001, MarketScope compares the primary Yahoo/yfinance annual return with an independently calculated Stooq annual return when both year-end anchors exist.

The comparison threshold defaults to 0.25 percentage points:

`absolute(Yahoo annual return - Stooq annual return) <= 0.25 pp`

Verification does not change the return used in simulations. Yahoo/yfinance remains authoritative for MarketScope calculations; Stooq disagreement is surfaced as a data-quality review flag.

## v5.9.58 dynamic completed-year history

The annual-history baseline is 2001 and the ending year is calculated at runtime as the latest completed calendar year.

For any completed year Y:

`annual return Y = adjusted year-end close Y / adjusted year-end close (Y-1) - 1`

The number of displayed annual columns is therefore:

`latest completed year - 2001 + 1`

This means the annual history grows by one column automatically after each calendar year closes. The daily refresh also expands `monthly_returns_full_history.csv` so withdrawal simulations retain genuine monthly paths for the same dynamically growing period.
## v5.9.59 monthly-withdrawal yearly reconciliation

The PDF year-level summary compounds the actual monthly portfolio returns for the calendar year. It does not use the December monthly return as a proxy for annual performance.

`Year Return = product(1 + monthly portfolio return) - 1`

Cash withdrawals are modeled separately. `End + Withdrawn` equals the December 31 remaining portfolio plus the cash withdrawn during that calendar year and is shown only as a cash-flow reconciliation measure. Because withdrawals occur throughout the year, that value is not used as the annual-return formula.

## v5.9.61 — $300K / $160K yearly-withdrawal ranking

The new high-withdrawal Top-100 family uses four equal-weight stocks from four different sectors and the ten completed annual-return columns in its saved CSV source.

For Rebalanced:
1. apply the equal-weight portfolio return for the year;
2. remove up to $160,000;
3. if funds remain, restore the four stocks to 25% each.

For Not Rebalanced:
1. apply each stock's annual return to its drifted holding;
2. remove up to $160,000 proportionally;
3. retain the post-withdrawal drifted weights.

Ranking priority is:
1. number of full $160,000 withdrawals funded;
2. total withdrawal cash delivered;
3. remaining ending balance.

Each ticker is capped at five appearances across each complete Top-100 list.
## v5.9.63 — 20Y $160K annual-withdrawal Top 250

The 20Y ranking uses completed annual returns from 2006 through 2025. Rebalanced portfolios apply the equal-weight portfolio return, take the annual withdrawal, then restore equal weights if capital remains. Not-Rebalanced portfolios apply each holding's return to drifted weights, take the withdrawal proportionally, and preserve drift.

Ranking order is full withdrawals funded, total cash delivered, then ending balance. Each ticker can appear no more than ten times in the complete Top 250 strategy list.
