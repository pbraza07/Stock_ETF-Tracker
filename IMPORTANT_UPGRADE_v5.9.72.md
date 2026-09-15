# MarketScope v5.9.72 — Annual Positive Years

## Requested change

For Yearly Withdrawal simulations, the fifth summary metric is now:

**POSITIVE YEARS — RB x/y | NR x/y**

instead of:

**WITHDRAWALS FUNDED — RB x/y | NR x/y**

This matches the existing Monthly Withdrawal behavior, which displays Positive Months.

## Definition

A Positive Year is a completed calendar year where that strategy's actual portfolio return is greater than 0%.

For each completed year:

`positive year = portfolio_return_pct > 0`

Exactly 0.00% is not counted as positive.

Current YTD partial rows are excluded.

## Strategy-specific calculation

Rebalanced and Not-Rebalanced are counted independently because their portfolio weights can diverge.

Example:

- Rebalanced: 15 positive years out of 17 modeled years → `RB 15/17`
- Not Rebalanced: 14 positive years out of 17 modeled years → `NR 14/17`

## Updated surfaces

Positive Years now replaces Withdrawals Funded in:

- Live Annual Withdrawal summary
- Save / Manage active Annual Withdrawal summary
- Saved Simulation inline withdrawal card
- Portfolio PDF page 1 Total Invested card

Monthly Withdrawal remains unchanged and continues to show:

**Positive Months — RB x/y | NR x/y**

## Saved records

New annual saved records retain:

- `annual_positive_years_rebalanced`
- `annual_positive_years_not_rebalanced`
- `annual_years_modeled_rebalanced`
- `annual_years_modeled_not_rebalanced`

Older saved simulations remain compatible. MarketScope derives Positive Years directly from their saved annual schedules when the explicit fields do not exist.

## Withdrawal-funding calculations remain available internally

The underlying withdrawal engine still tracks whether requested withdrawals were fully funded. That information remains available to ranking logic, depletion checks, detailed schedules, and historical ranking datasets.

Only the summary KPI requested by the user changes from withdrawal funding to annual return positivity.

## PDF

PDF layout is upgraded to **v30**. Rebuilt saved PDFs now show:

`POSITIVE YRS RB x/y NR x/y`

in the compact page-1 withdrawal summary.

No annual-return, withdrawal, rebalancing, monthly-return, price-target, or ranking methodology changed.
