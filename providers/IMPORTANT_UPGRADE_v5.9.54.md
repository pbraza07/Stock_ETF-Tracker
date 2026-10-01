# MarketScope v5.9.54 — Automatic 25-Year Annual History

The separate 25Y repair banner and **Repair 25Y annual history now** button are removed.

The same scheduled market snapshot refresh that updates price, YTD, 1D/1M/3M/6M, signals and the former 20 annual-return years now automatically owns all 25 completed calendar-year returns.

## Root fix

The oldest five annual columns require a prior-year price anchor. During 2026, displaying 2001 accurately requires adjusted daily history beginning in calendar 2000. v5.9.54 therefore requests Yahoo/yfinance adjusted daily history from **2000-01-01** explicitly instead of relying only on a large multi-symbol `period=max` response.

Long-history downloads are split into small batches and omitted symbols are retried individually.

## Durable preservation

A temporary Yahoo omission can no longer erase a previously verified annual return. Fresh values replace old values only when the new calculated annual return is valid; otherwise the durable prior annual value is retained. This lets 25Y coverage improve automatically across refreshes instead of reverting to blank cells.

## App-wide behavior

The automatic 25Y data feeds:
- Market Navigator Card View
- Market Navigator Table View
- Investment Simulator
- Portfolio Simulator
- Stock & ETF Comparison
- Sector Performance
- Worst Year calculations
- 1Y through 25Y historical simulations
- annual withdrawal simulations
- common-history calculations
- current year + prior 25 year charts
- saved Portfolio PDF rebuilds

Years before an instrument had sufficient full-year trading history remain blank. MarketScope does not manufacture pre-inception or partial-IPO calendar-year returns.

## Automatic refresh

GitHub Actions now sets `MARKETSCOPE_ANNUAL_HISTORY_START=2000-01-01` on every normal scheduled snapshot refresh. There is no separate 25Y user task.
