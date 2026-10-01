# MarketScope v5.9.6 - Portfolio Analytics & Enriched Saved PDFs

- Adds an instrument information/performance table immediately after a Portfolio Split simulation.
- Table fields: Industry, Stock, Allocation, 10-year CAGR, Positive years, Worst year %, Best year %, Regular yield, Estimated annual dividend, plus every MarketScope timeframe (1D, 1M, 3M, 6M, YTD and 10 completed calendar years).
- 10-year CAGR is derived from the ten completed calendar-year return factors when all ten years are available. It is not substituted for the card's individual annual returns.
- Regular yield is a trailing Yahoo dividend/distribution estimate. Estimated annual dividend equals allocated dollars multiplied by the saved trailing yield; it is not a forecast and excludes taxes/reinvestment.
- Saved simulation records now preserve all analytics and timeframe values, and PDFs add dedicated portfolio-information and timeframe-performance pages.
- Existing saved v5.9.5 records remain loadable; older PDFs simply lack the new supplemental tables.
