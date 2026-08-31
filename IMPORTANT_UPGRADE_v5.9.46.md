# MarketScope v5.9.46 - Actual Monthly Returns

## Monthly withdrawal simulations now use real monthly market returns

MarketScope no longer converts one annual return into twelve identical monthly rates.

For every stock and every modeled month, the monthly return is calculated from adjusted market history:

`month return = adjusted close at current month-end / adjusted close at prior month-end - 1`

January uses the prior December month-end adjusted close as its base.

This actual monthly series drives:
- Monthly withdrawal simulation
- Rebalanced monthly results
- Not-rebalanced monthly results
- Month-by-month PDF schedules
- The Top 100 monthly withdrawal ranking generator

## Durable monthly data

The scheduled GitHub Action now writes:

- `data/monthly_returns_10y.csv`
- `data/top100_rebalanced_monthly_withdrawal_10y_no_hwm.csv`
- `data/top100_not_rebalanced_monthly_withdrawal_10y_no_hwm.csv`

The ranking generator evaluates four-stock combinations from four different sectors, excludes HWM, starts at $300,000, withdraws $5,000 each month, and keeps only portfolios that fund all 120 withdrawals.

## First deployment step

After deploying v5.9.46, run the GitHub Actions workflow **Refresh MarketScope universe, snapshot and actual monthly rankings** once. A normal push to `main` also triggers it automatically.

Until the workflow finishes, MarketScope deliberately refuses to present the old approximate monthly ranking files as if they were actual-monthly rankings.

For a manually selected portfolio, MarketScope can fall back to an on-demand Yahoo/yfinance daily-history request if the durable monthly snapshot does not yet contain the required symbol/months.

## Saved PDF protection

All v5.9.40+ protections remain in force:
- `data/saved_portfolio_simulations.json`
- `data/generated_pdfs/`

Do not overwrite or delete these live-user-data paths during upgrades.
