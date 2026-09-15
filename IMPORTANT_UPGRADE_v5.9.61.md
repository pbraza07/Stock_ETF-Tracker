# MarketScope v5.9.61 — $160K Annual-Withdrawal Top 100

## New Portfolio Simulator ranking family

Portfolio Simulator now includes a third preset-row dropdown family:

**10Y $160K Withdrawal Top 100**

Assumptions:
- $300,000 starting portfolio
- exactly 4 stocks
- exactly 4 different sectors
- equal 25% starting allocation
- latest ten completed annual-return columns stored in the ranking source (2016–2025 for this release)
- $160,000 withdrawal after each annual return
- separate Rebalanced Annually and Not Rebalanced rankings
- each ticker can appear in no more than 5 of the Top 100 combinations in each strategy

## Ranking objective

$160,000 per year is an unusually aggressive withdrawal relative to a $300,000 starting balance. Therefore the optimizer ranks combinations by:

1. number of full $160,000 annual withdrawals funded;
2. total cash actually delivered;
3. ending portfolio balance.

The max-five ticker rule is then enforced while walking the ranking from best to lower-ranked combinations.

Every row explicitly shows:
- Target Withdrawals
- Withdrawals Fully Funded
- Full 10Y Withdrawal Goal
- Depleted Year
- Total Withdrawn
- Remaining Balance
- Net Value incl. Withdrawals
- Net Profit incl. Withdrawals
- all 10 annual portfolio returns
- all 10 balances after withdrawal
- Stock / Sector / Name for all four holdings
- each ticker's Top-100 use count
- Max Ticker Repeats
- Distinct Tickers in Top 100

## Current generated lists

Rebalanced:
- 100 combinations
- 84 distinct tickers
- maximum ticker use: 5
- 9 combinations fund all ten $160,000 withdrawals
- #1: PBR + TSLA + AMD + ANET
- #1 remaining after the 10th withdrawal: approximately $5.62M

Not Rebalanced:
- 100 combinations
- 82 distinct tickers
- maximum ticker use: 5
- 8 combinations fund all ten $160,000 withdrawals
- #1: PBR + DHR + NVDA + ANET
- #1 remaining after the 10th withdrawal: approximately $1.56M

## Reproducible ranking source

The release includes:
- `data/annual_performance_160k_source.csv`
- `scripts/build_160k_withdrawal_rankings.py`
- `data/top100_rebalanced_withdrawal_10y_160k_max5.csv`
- `data/top100_not_rebalanced_withdrawal_10y_160k_max5.csv`

Running the build script recreates both lists from the saved annual-performance source.

## Preset behavior

Choosing any combination automatically configures Portfolio Simulator to:
- $300,000 total portfolio
- 10Y
- Equal split
- Yearly withdrawal enabled
- Monthly withdrawal disabled
- $160,000 annual withdrawal

The existing $85K/year and $5K/month ranking families are unchanged.
