# MarketScope v5.4 deployment notes

v5.4 preserves the direct Nasdaq >$100B stock universe and ETF allowlist from v5.3, while adding 3Y annualized return, revised 1Y Avg, automatic column sizing, and short/long buy-signal detection.

The main table omits Inception Date and Exchange and orders return columns as: 1D, 1M, 3M, 6M, YTD, 1Y Avg, 3Y Avg, 5Y Avg, 10Y Avg.

The daily 6:00 PM U.S. Eastern GitHub Action refreshes Nasdaq ratings, adjusted market history, performance values, and signal state, then commits the persistent snapshot. Render reads that saved snapshot on startup.
