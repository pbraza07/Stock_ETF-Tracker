# MarketScope v5.9.50 - 25 Years of Annual Returns

MarketScope's app-wide completed-calendar-year history expands from 20 years to 25 years.

During 2026, the annual columns are:

2025, 2024, 2023, ... through 2001.

The change applies to:
- Market Navigator Card View
- Market Navigator Table View
- Investment Simulator
- Portfolio Split Simulator
- Portfolio common-history calculations
- Yearly withdrawal simulations
- Comparison cards and comparison tables
- Sector Performance ranking horizons and annual-return tables
- Open Instrument year-by-year historical chart
- Portfolio Simulator PDF combined timeframe performance
- Daily GitHub snapshot refresh

Historical-horizon controls now expose YTD plus 1Y through 25Y. Instruments without the full history are not given fabricated returns; MarketScope continues to use only valid common completed years.

The 5Y/10Y ranked-combination datasets and the 10Y actual-monthly withdrawal ranking datasets remain 5Y/10Y products and are not changed into 25Y rankings.

## Data refresh

The scheduled snapshot job now requests 25 completed calendar-year returns from max adjusted-price history. After deploying v5.9.50, the next successful MarketScope refresh will populate the five newly added historical years where each instrument has genuine coverage.

## Persistence

Saved Portfolio Simulation records and generated PDFs remain protected under the existing durable GitHub persistence rules.

## Saved Portfolio PDFs

The Portfolio PDF layout is bumped to v13. Opening an older saved simulation now refreshes each instrument's saved performance map from the current MarketScope snapshot, so the rebuilt PDF can show the full 25 completed annual-return years when those values are available.
