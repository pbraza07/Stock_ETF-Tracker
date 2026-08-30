# MarketScope v5.9.38 — Rebalanced vs Not-Rebalanced Annual Withdrawals

- Annual withdrawal simulations now calculate two strategies from the same starting allocation and historical return window.
- **Rebalanced annually:** after each completed calendar year return and withdrawal, the remaining portfolio is reset to the original target weights.
- **Not rebalanced:** after each return and proportional withdrawal, holding weights are allowed to drift.
- Portfolio Simulator displays separate tables for both strategies and a side-by-side annual comparison.
- Summary metrics show the ending balance under each strategy and the difference.
- Saved simulations persist both schedules while legacy withdrawal fields remain mapped to the not-rebalanced path for backward compatibility.
