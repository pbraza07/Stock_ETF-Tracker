# MarketScope v5.9.63 — 20Y $160K Withdrawal Top 250

## New Portfolio Simulator family

A new preset family is available under Portfolio Simulator:

**20Y $160K Withdrawal Top 250**

Rules:
- $300,000 starting portfolio
- $160,000 annual withdrawal
- 20 completed calendar years: 2006–2025
- exactly 4 stocks
- exactly 4 different sectors
- 25% starting allocation per stock
- separate Rebalanced Annually and Not Rebalanced rankings
- maximum 10 appearances per ticker across each full Top 250 list

## Ranking objective

Because $160,000 per year is extremely aggressive relative to a $300,000 starting portfolio, the ranking is income-survival first:

1. number of full $160,000 annual withdrawals funded;
2. total withdrawal cash actually delivered;
3. ending portfolio balance.

The list then enforces the max-10 ticker-use rule while preserving highest-ranked eligible combinations.

## Current generated results

The complete-history source contains 135 stocks across 11 sectors, producing 5,219,538 distinct-sector four-stock combinations.

No eligible portfolio funds all 20 full withdrawals. The highest-ranked combinations fund six full $160,000 withdrawals before depletion. This is displayed explicitly rather than hidden.

Rebalanced Top 250:
- 250 portfolios
- 104 distinct tickers
- maximum ticker use = 10
- best full-withdrawal count = 6/20
- #1: AEM + BKNG + MNST + ISRG
- actual cash withdrawn before depletion: approximately $1.077M

Not Rebalanced Top 250:
- 250 portfolios
- 103 distinct tickers
- maximum ticker use = 10
- best full-withdrawal count = 6/20
- #1: SCCO + BKNG + MNST + NVO
- actual cash withdrawn before depletion: approximately $1.106M

## Packaged assets

- `data/annual_performance_20y_160k_source.csv`
- `data/top250_rebalanced_withdrawal_20y_160k_max10.csv`
- `data/top250_not_rebalanced_withdrawal_20y_160k_max10.csv`
- `scripts/build_20y_160k_withdrawal_rankings.py`

Selecting a preset automatically sets the simulator to $300,000, 20Y, Equal Split, Yearly Withdrawal enabled, $160,000/year.
