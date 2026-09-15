# MarketScope v5.9.74 — Annual Reset Inside Yearly Withdrawal Tabs

## Placement

Following the requested reference image, the yearly-withdrawal result section now has four tabs in this order:

1. **↻ Rebalanced annually**
2. **↝ Not rebalanced**
3. **⚖ Side-by-side**
4. **📅 Annual Reset**

The separate top-level **Annual Reset Performance** workspace from v5.9.73 has been removed.

Portfolio Simulator therefore returns to the top-level workspace structure:

- **◆ Build Simulation**
- **💾 Saved / Manage**

## Annual Reset with withdrawal

Annual Reset continues to be an independent one-year experiment.

For every eligible completed year:

1. reset the portfolio to the same original starting investment;
2. reset holdings to the current target allocation;
3. apply that calendar year's actual saved return for every selected stock/ETF;
4. calculate the allocation-weighted portfolio annual return;
5. calculate Gain / Loss;
6. calculate value Before Withdrawal;
7. apply the current Annual Withdrawal;
8. show Remaining After Withdrawal;
9. discard that ending balance before calculating the next calendar year.

Nothing carries forward.

## Reference-table layout

The reset table follows the annual-withdrawal table shown in the reference image and includes:

- Year
- Starting Balance
- each selected stock/ETF's Annual Return
- Annual Return
- Gain / Loss
- Before Withdrawal
- Withdrawal
- Remaining After Withdrawal
- Withdrawal Status

## Withdrawal handling

The requested annual withdrawal is applied after the year's annual return.

If the year's portfolio value can fund the entire withdrawal:

`Withdrawal Status = Funded`

If it can only fund part of the request:

`Withdrawal Status = Partial`

If no amount can be funded:

`Withdrawal Status = Not funded`

A partial or failed withdrawal does **not** affect any subsequent reset row. The next year still starts from the original investment.

## Year eligibility

The reset view uses the current Portfolio Simulator's completed-year window and includes a year only when every selected instrument has a finite annual return.

It does not:

- use YTD partial as an annual-reset row;
- fill pre-IPO years;
- invent missing annual returns;
- use only part of the selected portfolio.

## Allocation

Annual Reset uses the current allocation selected in Build Simulation.

For Equal Split with four stocks, every row starts again at 25% / 25% / 25% / 25%.

Custom allocation is supported when it totals 100%.

## Summary metrics

Inside the Annual Reset tab MarketScope displays:

- Reset Start Each Year
- Annual Withdrawal
- Eligible Years
- Positive Years
- Withdrawal Funded
- Best / Worst annual return

## Existing calculations

No changes were made to the normal rolling:

- Rebalanced annual-withdrawal path
- Not-Rebalanced annual-withdrawal path
- Side-by-Side comparison
- Monthly withdrawals
- annual-return data
- actual monthly-return data
- portfolio rankings
- price targets
- saved simulation persistence

PDF layout is bumped to **v32** so rebuilt saved PDFs identify MarketScope v5.9.74. The Annual Reset table remains an interactive Build Simulation view and is not added as a separate PDF page in this release.
