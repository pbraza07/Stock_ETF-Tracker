# MarketScope v5.9.57 - 25Y Withdrawal Source Fix

## LLY monthly-withdrawal error fixed

The previous monthly simulator could fail with:

`Actual monthly history is unavailable for: LLY`

even when LLY had valid annual-return history in Market Table.

v5.9.57 removes that fragile dependency by creating a durable **25-year actual monthly-return dataset** from the same adjusted Yahoo/yfinance daily history that produces the Market Table annual returns.

The normal snapshot refresh now writes both:

- `data/monthly_returns_10y.csv` — retained for the existing 10Y Top 100 ranking engine
- `data/monthly_returns_25y.csv` — actual monthly history for 2001–2025 withdrawal simulations

The 25Y file is persisted in the same race-safe checkpoint as the annual market snapshot.

## No synthetic monthly returns

Monthly withdrawals still use genuine adjusted month-end returns. MarketScope does not divide, average or root annual returns into synthetic monthly rates.

For each completed year, the 12 actual monthly returns are compounded and checked against the exact annual return displayed in Market Table. The monthly schedule is allowed to run only when the histories reconcile within 0.05 percentage points.

If a durable monthly row is missing, MarketScope now:
1. checks the 25Y monthly dataset;
2. checks the legacy 10Y monthly dataset;
3. checks their GitHub copies;
4. downloads explicit-start Yahoo history back to 2000;
5. retries missing symbols individually.

This specifically prevents one Yahoo batch omission from invalidating the entire portfolio.

## Market Table withdrawal simulator

Market Table now includes an optional **Table yearly withdrawal** simulation.

It uses the exact annual return columns already displayed in Table View.

For a 25Y selection:
- 2001 is processed first;
- then 2002, 2003, ...;
- 2025 is processed last;
- the requested withdrawal is taken after each completed year's return.

New Table View columns include:
- Withdraw / Yr
- Return Years Used
- Withdrawals Funded
- Total Withdrawn
- Remaining After Withdrawals
- Net Value incl. Withdrawals
- Net Profit incl. Withdrawals

An instrument without the full selected history remains unavailable rather than receiving fabricated pre-IPO returns.

## Portfolio annual withdrawals

Portfolio Simulator yearly withdrawals continue to support Rebalanced and Not Rebalanced modes, but the source is now explicitly identified as the exact Market Table annual-return columns.

A 25Y Portfolio Simulator selection uses all 25 common completed years where every selected instrument has genuine history.

## PDF

Portfolio PDF layout is upgraded to **v16**.

Annual withdrawal schedules are now paginated instead of being truncated at 21 rows, so a full 25-year withdrawal simulation appears completely in the PDF.

Monthly PDF methodology text now states that the actual monthly path is reconciled to Market Table annual returns.

## Automatic reconciliation gate

Before the annual snapshot and 25Y monthly file are persisted, `scripts/validate_25y_monthly.py` compounds each available set of 12 monthly returns and compares it with the corresponding Market Table annual return. The workflow stops rather than persist inconsistent withdrawal-source data when the difference is above 0.05 percentage points or a full-year annual return lacks the required 12 monthly anchors.
