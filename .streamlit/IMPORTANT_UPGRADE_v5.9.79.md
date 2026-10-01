# MarketScope v5.9.79 — Monthly Reset + Monthly Start-Year Paths

## Monthly Withdrawal tab row

The Monthly Withdrawal section now permanently contains six tabs:

- ↻ Rebalanced monthly
- ↝ Not rebalanced monthly
- ⚖ Monthly side-by-side
- 📅 Monthly Reset
- 📈 Monthly Start-Year Rebalanced
- 📉 Monthly Start-Year Not Rebalanced

The tabs remain visible even when Monthly Withdrawal is disabled or monthly data is temporarily unavailable.

## Monthly Reset

Every historical month independently starts with the same original investment and target allocation, applies each instrument's actual adjusted month-end return, and takes one monthly withdrawal. No balance or profit carries into the next reset row.

## Monthly Start-Year paths

Each eligible Start Year creates a cohort beginning in January with the same original investment. From then forward:

1. Actual instrument monthly returns are applied.
2. The selected monthly withdrawal is taken.
3. Remaining After Withdrawal carries into the next month.
4. December carries directly into January; there is no annual reset.
5. Rebalanced restores target weights after each monthly withdrawal.
6. Not Rebalanced preserves drifted holding weights.

Both separate strategy tables show Start Year, Month, Month number, monthly return, gain/loss, withdrawal, remaining balance, cumulative withdrawals, cumulative Profit ($), Profit (%), and withdrawal funding status.

## Depletion dashboard

Both Monthly Start-Year tabs retain the five large KPI cards and add a separate two-column row for:

- RB First Depletion Month
- NR First Depletion Month

A cohort is depleted when Remaining After Withdrawal is at or below $0.005. Each card identifies the earliest affected Start-Year cohort and the number of depleted cohorts.

## Data integrity

Monthly paths use actual adjusted month-end returns and retain the existing annual-reconciliation gate. Annual returns are never divided or rooted into synthetic monthly values.

PDF layout is bumped to v37 so rebuilt saved PDFs identify MarketScope v5.9.79.
