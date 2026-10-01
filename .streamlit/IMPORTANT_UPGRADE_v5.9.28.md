# MarketScope v5.9.28 — Annual Withdrawal Schedule

- Adds an **Annual withdrawals** toggle to Portfolio Simulator for 1Y–20Y historical simulations.
- Adds a configurable annual withdrawal amount.
- Applies each instrument's saved return first, then removes the withdrawal proportionally from the post-return portfolio.
- Shows a year-by-year schedule: starting balance, annual portfolio return, gain/loss, pre-withdrawal balance, withdrawal, and remaining balance.
- Shows total withdrawn, final remaining balance, and remaining balance + cumulative withdrawals.
- Stops the path and clearly flags the year if the portfolio is depleted.
- Current YTD can be included as a final partial-period row but does not trigger another annual withdrawal.
- Persists withdrawal settings and schedule in Saved Simulations and adds the schedule to the generated PDF.
- Preserves all v5.9.27 ranked 4-stock combo functionality.
