# MarketScope v5.9.62 — Responsive Yearly Withdrawal + Compact Simulator KPIs

## Yearly Withdrawal now matches Monthly Withdrawal

The Yearly Withdrawal comparison no longer uses four native `st.metric()` widgets. It now uses the same responsive card system as Monthly Withdrawal.

The five yearly cards are:
- Annual withdrawal
- Rebalanced remaining
- Not rebalanced remaining
- Rebalance difference
- Withdrawals funded (`RB x/y` and `NR x/y`)

The funded count excludes the optional partial YTD row and counts a year only when the full requested annual withdrawal was actually paid. This is especially useful for the $160K/year ranking presets because portfolio depletion is visible immediately.

## Main Portfolio Simulator totals are compact

The old native metrics shown after allocation calculation caused very tall one-card-per-row blocks on mobile. They are replaced with the same responsive card language used by the withdrawal summary.

The four cards are:
- Portfolio invested
- Calculated ending value
- Calculated profit / loss
- Calculated return

Desktop shows four cards in one row. Medium widths use a 2×2 grid. Phone widths use one compact card per row with reduced height and padding, avoiding the oversized layout shown in the prior mobile screenshot.

## No calculation changes

The underlying portfolio return, annual-withdrawal, monthly-withdrawal, rebalancing, and ranking calculations are unchanged. This release changes presentation and adds the annual funded-count summary only.

## PDF version

The saved/rebuilt Portfolio PDF contract is bumped to v21 so page 1 identifies MarketScope v5.9.62.
