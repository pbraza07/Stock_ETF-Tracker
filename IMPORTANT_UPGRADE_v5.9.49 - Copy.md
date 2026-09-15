# MarketScope v5.9.49 - Positive Months Fix

## What was fixed

v5.9.48 calculated actual monthly portfolio returns correctly, but the monthly withdrawal result dictionary did not persist `positive_months` and `months_modeled`. The Portfolio Simulator metric therefore read missing fields and displayed `0/0` even when many months were positive.

v5.9.49 repairs that contract end to end:

- Rebalanced Monthly now returns and persists its true positive-month count.
- Not Rebalanced Monthly now returns and persists its true positive-month count.
- Positive Months in the Portfolio Simulator summary no longer defaults to zero because of a missing result field.
- The Top 100 monthly combination tables always expose Positive Months near the front of the table and display it as `positive / months funded` (for example `78/120`).
- Older actual-monthly Top 100 files are recalculated when Positive Months is missing, blank, invalid, or greater than Months Funded.
- The Portfolio Information & Performance Table continues to show each selected stock's positive months from actual adjusted month-end returns.
- New saved simulation records persist each instrument's `positive_months` and `available_months`.

## PDF changes

The Portfolio Simulator PDF layout is now v12 so older saved PDFs rebuild automatically.

Positive Months now appears in three visible places:

1. Page 1 - Combined Portfolio Performance: `POS MONTHS` shows Rebalanced and Not Rebalanced counts.
2. Monthly Withdrawals - Strategy Comparison: a dedicated `POSITIVE MONTHS` summary card shows both strategy counts.
3. Portfolio Information Table: each instrument has a `POS MONTHS` column.

Older v5.9.48 saved simulations are repaired from their existing real monthly schedules during PDF rebuild, so they do not remain stuck at zero.

## Methodology

A positive month is a modeled month whose portfolio return before the withdrawal is greater than 0%. The return is calculated from actual adjusted month-end market returns. The $5,000 withdrawal itself does not determine whether a month is positive or negative.

## Persistence protection

The existing upgrade protections remain unchanged. Do not overwrite or delete:

- `data/saved_portfolio_simulations.json`
- `data/generated_pdfs/`
