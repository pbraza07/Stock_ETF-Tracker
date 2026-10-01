# MarketScope v5.9.69 — Saved Simulation Inline Withdrawal Summary

## Exact requested placement

Under **SAVE / MANAGE PORTFOLIO SIMULATIONS**, withdrawal results now live inside the same Saved Simulation card that contains:

- Invested
- Ending
- Profit / Loss
- Return

They are no longer rendered as a separate full-width withdrawal section below that card.

The new compact row occupies the area directly beneath the primary metrics (the red-arrow location in the request).

## Yearly Withdrawal saved cards

The card displays:

- Annual Withdrawal
- Rebalanced Remaining
- Not-Rebalanced Remaining
- Rebalance Difference
- Withdrawals Funded — `RB x/y` and `NR x/y`

## Monthly Withdrawal saved cards

The card displays:

- Monthly Withdrawal
- Rebalanced Remaining
- Not-Rebalanced Remaining
- Rebalance Difference
- Positive Months — `RB x/y` and `NR x/y`

## Typography and responsive layout

The primary Saved Simulation values remain at approximately `.92rem`.

The new withdrawal values use a smaller `.76rem` value font with `.56rem` labels, matching the compact information style requested.

Desktop:
- primary row remains unchanged
- withdrawal row spans the metric area beneath Invested / Ending / Profit-Loss / Return
- five withdrawal metrics appear horizontally

Tablet:
- withdrawal metrics collapse into two columns

Mobile:
- withdrawal metrics collapse into one column and remain fully visible

## Compatibility

Existing saved annual/monthly simulations are supported. MarketScope derives legacy funded counts from their saved schedules when explicit counts are absent.

No return, rebalancing, withdrawal, price-target, or PDF calculation methodology changed in v5.9.69.

## PDF

The Portfolio PDF contract is bumped to **v27** only so rebuilt saved PDFs identify the current MarketScope release. The v5.9.68 PDF page-1 withdrawal summary and Market Table price-target transcription remain intact.
