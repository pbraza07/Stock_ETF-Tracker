# MarketScope v5.9.51 — Hidden Ranking Buttons + Recession-Balanced Portfolios

## Portfolio Simulator ranking buttons

The ranking families are hidden until their own button is opened:

- 5Y Combo Rankings
- 10Y Combo Rankings
- 10Y Yearly Withdrawal
- 10Y Actual-Monthly Withdrawal
- Recession-Balanced Top 100

This keeps the Portfolio Simulator compact while preserving every prior preset.

## Recession-Balanced Top 100

Two new Top 100 ranking lists are included:

- Rebalanced Annually
- Not Rebalanced

Each portfolio contains exactly four stocks from four different sectors:

- Stock 1 + Stock 2: **Profit Engine** role. Candidates are screened on the 2016–2025 annual-return path for positive compounded growth and at least 6 positive years out of 10, then ranked by compounded growth.
- Stock 3 + Stock 4: **Recession Defense** role. Candidates are screened on annual returns that overlap official NBER recession periods. The defense ranking is maximin first (strongest worst recession-stress result), then average recession-stress return, then positive recession observations.

Official NBER periods used by the model:

- March–November 2001
- December 2007–June 2009
- February–April 2020

Because the source is annual performance, MarketScope maps these periods to available annual stress years: 2001, 2008, 2009 and 2020. A year is used only when the source actually contains that stock's annual return. The current package fallback source contains 2008, 2009 and 2020; after the 25-year snapshot refresh, 2001 is also incorporated where available.

NBER source:
https://www.nber.org/research/data/us-business-cycle-expansions-and-contractions

The recession-balanced ranking simulation uses a $300,000 equal-weight start, 2016–2025 performance, and no cash withdrawals so the ranking isolates growth plus the historical recession-defense screen. Rebalanced resets to 25% per stock annually; Not Rebalanced lets holdings drift.

## Detailed Rebalanced / Not-Rebalanced tables

All Rebalanced / Not-Rebalanced ranking families now expose the detailed field structure used by the original 10Y $300K / $85K yearly-withdrawal ranking:

- rank / combo / strategy
- Stock 1–4
- Sector 1–4
- Name 1–4
- strategy-specific annual returns
- worst year / worst %
- best year / best %
- starting value
- yearly or monthly withdrawal amount
- total withdrawn
- remaining balance
- net value including withdrawals
- net profit including withdrawals
- year-by-year ending / post-withdrawal balances

Actual-monthly tables additionally show Positive Months and Months Funded. Recession-balanced tables additionally show each stock's assigned role and recession-defense metrics.

## Automatic refresh

The daily GitHub workflow rebuilds the recession-balanced rankings after refreshing the annual-return snapshot. The generator supports MarketScope annual data with either Symbol/Sector fields or export-style Stock/Industry fields.

Saved Portfolio Simulation and PDF persistence protections remain unchanged.
