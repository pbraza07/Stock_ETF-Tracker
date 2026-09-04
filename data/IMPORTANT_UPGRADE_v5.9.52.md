# MarketScope v5.9.52 — Recession Top 100 Max-5 Diversification

The Recession-Balanced Top 100 rankings are regenerated with a hard concentration limit:

- exactly 4 stocks
- exactly 4 different sectors
- exactly 2 Profit Engine stocks
- exactly 2 Recession Defense stocks
- no ticker may appear in more than 5 of the selected Top 100 combinations
- the cap is enforced separately for Rebalanced Annually and Not Rebalanced rankings

The old v5.9.51 20/20 candidate pools were expanded to 100 Profit Engine candidates and 100 Recession Defense candidates so the optimizer can fill 100 genuinely diversified portfolios while preserving high historical profit.

The ranking engine first scores a broad set of high-profit role-compatible combinations, then selects the highest-profit eligible portfolios subject to the max-five ticker-usage constraint.

The output tables now include:
- Stock 1–4 Top100 Uses
- Max Ticker Repeats
- Distinct Tickers in Top 100

Current packaged ranking QA:
- Rebalanced: 100 portfolios, 84 distinct tickers, maximum use = 5
- Not Rebalanced: 100 portfolios, 84 distinct tickers, maximum use = 5

All prior MarketScope persistence protections remain unchanged.
