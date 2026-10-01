# MarketScope v5.9.76 — Start-Year Rolling Withdrawal Paths

## New fifth tab in Build Simulation

The annual-withdrawal tab row is now:

1. **↻ Rebalanced annually**
2. **↝ Not rebalanced**
3. **⚖ Side-by-side**
4. **📅 Annual Reset**
5. **📈 Start-Year Paths**

The fifth tab is persistent just like the other annual tabs.

## What Start-Year Paths calculates

This is different from Annual Reset.

### Annual Reset
Every row starts over from the original investment.

### Start-Year Paths
Only the first row of a cohort starts from the original investment.

After that:

`Next Year Starting Balance = Prior Year Remaining After Withdrawal`

The balance therefore rolls forward through all subsequent eligible years.

## Example

Assume:

- Initial investment: $300,000
- Annual withdrawal: $70,000
- Start Year: 2022

The 2022 row begins at $300,000.

If 2022 ends with $260,000 after withdrawal, then:

- 2023 starts at $260,000
- 2023 return is applied to $260,000
- 2023 withdrawal is taken
- the new remaining balance becomes the 2024 starting balance
- and so on

A separate 2023 cohort independently begins at the original $300,000 and then rolls forward from 2023 onward.

## One combined table

Both annual strategies are included in the same table:

- Rebalanced annually
- Not rebalanced

The table includes:

- Start Year
- Year
- Year #
- Strategy
- Starting Balance
- Annual Return
- Year Gain / Loss
- Before Withdrawal
- Withdrawal
- Remaining After Withdrawal
- Cumulative Withdrawn
- Profit
- Profit %
- Withdrawal Status

## Profit definition

Profit is cumulative economic profit versus the original starting investment and includes cash already withdrawn:

`Profit = Remaining After Withdrawal + Cumulative Withdrawn − Initial Investment`

`Profit % = Profit ÷ Initial Investment`

This prevents withdrawals from being incorrectly treated as lost value.

## Year eligibility

Only completed calendar years where every selected instrument has a valid annual return are used.

The analysis stays within the current Portfolio Simulator completed-year window.

No missing annual returns are invented.

## Rebalanced vs Not-Rebalanced

For each Start Year, MarketScope calculates both:

- Rebalanced annually
- Not rebalanced

Rebalanced restores the target weights after each annual withdrawal.

Not rebalanced allows the holdings to drift naturally.

## Persistence of the tab row

If Yearly Withdrawal is turned off, the fifth tab remains visible with the other annual tabs and explains what must be enabled to populate the table.

## Existing calculations

No changes were made to:

- annual return data
- standard rolling annual-withdrawal paths
- Annual Reset formulas
- monthly withdrawals
- rankings
- price targets
- saved simulation persistence

PDF layout is bumped to **v34** so rebuilt saved PDFs identify MarketScope v5.9.76. The Start-Year Paths table is currently an interactive simulator analysis and is not added as a separate PDF page.
