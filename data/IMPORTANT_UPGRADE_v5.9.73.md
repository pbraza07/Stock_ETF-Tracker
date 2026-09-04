# MarketScope v5.9.73 — Annual Reset Performance

## New Portfolio Simulator workspace tab

Portfolio Simulator now has three top-level workspaces:

1. **Build Simulation**
2. **Annual Reset Performance**
3. **Saved / Manage**

## What Annual Reset Performance means

This is deliberately **not** a compounded multi-year simulation.

Every eligible calendar year starts over with exactly the same original portfolio investment.

Example with a $300,000 portfolio:

- 2019 starts with $300,000
- calculate only the 2019 portfolio return
- show 2019 ending value and profit/loss
- discard that ending value for the reset experiment
- 2020 starts again with $300,000
- repeat for every eligible completed year

A profitable 2019 therefore does not increase the 2020 starting amount.

A losing 2019 also does not reduce the 2020 starting amount.

## Allocation

The table uses the current Portfolio Simulator allocation:

- Equal Split, or
- the current valid Custom % allocation

The same allocation is restored at the beginning of every annual row.

For a four-stock equal-weight portfolio, every row begins 25% / 25% / 25% / 25%.

## Year eligibility

A year appears only when **every selected stock or ETF has a finite completed calendar-year return**.

MarketScope does not:

- invent missing annual returns
- fill pre-IPO years
- mix partial portfolios
- calculate a year using only some selected holdings

If one selected instrument has no return for 2012, the entire 2012 portfolio row is excluded.

The table automatically uses all shared completed annual history available in MarketScope, independent of the compounded period currently selected in Build Simulation.

## Table layout

Following the requested annual-performance table reference, each row includes:

- Year
- Initial Investment
- one annual-return column for every selected stock / ETF
- Portfolio Return
- Ending Value
- Profit / Loss
- Result: Positive / Negative / Flat

## Formula

For each year:

`Portfolio Return = Σ (target weight × stock annual return)`

`Ending Value = Reset Starting Investment × (1 + Portfolio Return)`

`Profit / Loss = Ending Value − Reset Starting Investment`

Then the calculation resets before the next year.

## Summary

The tab also shows:

- Reset Start Each Year
- Eligible Years
- Positive Years
- Best Year
- Worst Year
- Average independent one-year return

The average is descriptive only and is explicitly not labeled as a compounded return.

## Existing functionality

No changes were made to:

- normal compounded Portfolio Simulation
- Yearly Withdrawal
- Monthly Withdrawal
- Rebalanced / Not-Rebalanced withdrawal paths
- annual-return source data
- actual monthly returns
- ranking datasets
- Market Table
- price targets
- saved Portfolio Simulation persistence

The PDF contract is bumped to **v31** so rebuilt saved PDFs identify MarketScope v5.9.73. The Annual Reset table itself is currently an interactive Portfolio Simulator tab and is not added as a new PDF page in this release.
