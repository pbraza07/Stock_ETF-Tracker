# MarketScope v5.9.78 — Start-Year RB/NR Depletion Dashboard

## Requested dashboard addition

The rolling Start-Year dashboard keeps its existing five large KPI cards exactly as they are:

- Initial Investment
- Annual Withdrawal
- Start-Year Cohorts
- Earliest / Latest
- Path Rows

No sixth KPI was squeezed into that row.

Immediately below it, MarketScope now renders a separate two-column depletion row:

- **RB First Depletion Year**
- **NR First Depletion Year**

This preserves the size and readability of the original dashboard numbers.

## Depletion definition

A rolling Start-Year cohort is considered depleted when:

`Remaining After Withdrawal <= $0.005`

The dashboard reports the earliest calendar year in which any cohort reaches that condition.

Because multiple Start-Year cohorts are modeled, each depletion card also shows:

- the Start Year of the earliest affected cohort; and
- the number of depleted cohorts out of the total modeled cohorts.

Example:

**RB First Depletion Year: 2022**  
`Earliest affected start cohort: 2015 • Depleted cohorts: 4/11`

If no cohort depletes:

**Not depleted**  
`All modeled cohorts survived • Depleted cohorts: 0/11`

## Strategy comparison

Both depletion cards are shown in both Start-Year strategy tabs so Rebalanced and Not-Rebalanced depletion can be compared immediately without switching back and forth just to find the other strategy's depletion year.

The underlying Start-Year tables remain separated:

- Start-Year Rebalanced
- Start-Year Not Rebalanced

## No methodology changes

This release adds only the depletion summary. It does not change:

- annual return calculations
- annual withdrawal ordering
- Rebalanced calculations
- Not-Rebalanced calculations
- Start-Year cohort rolling logic
- cumulative profit formula
- Annual Reset
- monthly withdrawals
- ranking data
- saved simulation persistence

PDF layout is bumped to **v36** so rebuilt saved PDFs identify MarketScope v5.9.78.
