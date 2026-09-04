# MarketScope v5.9.47

## Actual monthly Top 100 rankings are now the only monthly preset source

Portfolio Simulator keeps these two monthly ranking dropdowns:

- Top 100 — Rebalanced Monthly (Actual Returns)
- Top 100 — Not Rebalanced Monthly (Actual Returns)

Ranking assumptions:
- $300,000 starting portfolio
- exactly 4 stocks
- 4 different sectors
- HWM excluded
- equal 25% initial allocation
- $5,000 withdrawn at the end of every month
- 120 withdrawals across the latest 10 completed calendar years
- only portfolios that fund all 120 withdrawals and remain above $0 qualify
- ranked by remaining balance after month 120

Every month uses the actual adjusted month-end return from Yahoo/yfinance daily history. Annual returns are never divided into monthly rates.

## Portfolio Simulator withdrawal controls

The controls remain explicitly separated and mutually exclusive:

- Yearly withdrawal
- Monthly withdrawal

Selecting an actual-monthly Top 100 preset automatically configures $300,000 / 10Y / Equal split / Monthly withdrawal / $5,000 per month.

## Important reliability fix

GitHub commits that save Portfolio Simulation records or generated PDFs no longer trigger the long market-data refresh workflow. This prevents PDF saves from repeatedly cancelling the actual-monthly Top 100 ranking job before it finishes.

Ignored refresh-trigger paths now include:
- data/saved_portfolio_simulations.json
- data/generated_pdfs/**
- static/generated_pdfs/**

Saved PDF persistence protections remain unchanged.
