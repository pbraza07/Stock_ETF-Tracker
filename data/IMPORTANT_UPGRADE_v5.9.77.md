# MarketScope v5.9.77 — Split Start-Year Rebalanced / Not-Rebalanced Tabs

## Requested clarification

The combined **📈 Start-Year Paths** tab from v5.9.76 has been split into two separate tabs:

1. **📈 Start-Year Rebalanced**
2. **📉 Start-Year Not Rebalanced**

They remain in the same annual-withdrawal tab row immediately after **📅 Annual Reset**.

The full row is now:

- ↻ Rebalanced annually
- ↝ Not rebalanced
- ⚖ Side-by-side
- 📅 Annual Reset
- 📈 Start-Year Rebalanced
- 📉 Start-Year Not Rebalanced

## Start-Year Rebalanced

Each eligible cohort:

- starts with the same original investment in its Start Year;
- applies that year's annual returns;
- takes the current annual withdrawal;
- carries Remaining After Withdrawal into the next year;
- restores holdings to the original target weights after each yearly withdrawal.

The balance rolls forward. Only the weights are rebalanced.

## Start-Year Not Rebalanced

Each eligible cohort:

- starts with the same original investment in its Start Year;
- applies that year's annual returns;
- takes the current annual withdrawal;
- carries Remaining After Withdrawal into the next year;
- keeps the drifted holding weights.

No annual rebalance is performed.

## Separate tables

The Strategy column is removed because each tab now represents exactly one strategy.

Both tables retain:

- Start Year
- Year
- Year #
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

Profit remains cumulative economic profit:

`Profit = Remaining After Withdrawal + Cumulative Withdrawn − Original Investment`

`Profit % = Profit ÷ Original Investment`

## Persistent visibility

Both Start-Year tabs remain visible when Yearly Withdrawal is off or temporarily unavailable, consistent with v5.9.75.

No annual-return, withdrawal, ranking, price-target, monthly-return, or persistence calculations changed.

PDF contract is bumped to **v35** so rebuilt saved PDFs identify MarketScope v5.9.77.
