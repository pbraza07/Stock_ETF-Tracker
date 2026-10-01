# MarketScope v5.9.59 - Monthly PDF Yearly Cash-Flow Reconciliation

The Monthly Withdrawals - Strategy Comparison page has been redesigned to make the annual results mathematically understandable.

## Misleading December return removed

The previous comparison table displayed `REBAL. DEC RETURN` and `NOT REBAL. DEC RETURN`. Those values were only the portfolio return for December, but they appeared next to a full calendar-year ending balance and could easily be interpreted as the return for the entire year.

v5.9.59 removes those columns.

## True yearly return

For each calendar year and each strategy, the PDF now calculates the time-weighted annual portfolio return by compounding the actual monthly portfolio returns:

`Year Return = product(1 + monthly return Jan ... Dec) - 1`

This calculation is performed before cash-withdrawal effects. It is therefore a genuine investment-performance return rather than a return inferred from the ending balance after withdrawals.

## New yearly cash-flow reconciliation table

Each calendar-year row now includes:

- Start Balance - Rebalanced / Not Rebalanced
- Year Return - Rebalanced / Not Rebalanced
- Year Withdrawn - actual cash paid during that year for each strategy
- Rebalanced Year-End Remaining
- Rebalanced End + Withdrawn
- Not-Rebalanced Year-End Remaining
- Not-Rebalanced End + Withdrawn
- Total Value Difference

`End + Withdrawn` means the December 31 remaining portfolio plus the cash actually withdrawn during that same calendar year. It is included to make the yearly cash flow easy to reconcile.

Because withdrawals occur monthly, `End + Withdrawn` is **not** used to calculate Year Return. The PDF states this directly on the comparison page.

## Summary metrics

The top of the page now shows:

- Monthly Withdrawal
- Full-Year Cash Target = monthly withdrawal x 12
- Rebalanced Remaining
- Not-Rebalanced Remaining
- Remaining Difference
- Positive Months

The bottom of the page also shows cumulative withdrawals and `remaining + cumulative withdrawals` for both strategies.

## PDF version

Saved Portfolio PDFs now use layout **v18** so older saved simulations automatically rebuild into the clearer comparison layout.
