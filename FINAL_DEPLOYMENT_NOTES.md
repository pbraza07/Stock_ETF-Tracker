# MarketScope v5.9.40 - Final Deployment Notes

Parent release: MarketScope v5.9.38.

## Change
Portfolio Simulator PDFs now include the annual-withdrawal comparison that was already available in the app:

1. Strategy comparison page
   - Annual withdrawal
   - Rebalanced remaining balance
   - Not-rebalanced remaining balance
   - Rebalance difference
   - Year-by-year side-by-side return and remaining balance
2. Detailed Rebalanced annual-withdrawal schedule
3. Detailed Not Rebalanced annual-withdrawal schedule

Each detailed table includes Year, Starting Balance, Portfolio Return, Gain/Loss, Balance Before Withdrawal, Withdrawal, and Remaining Balance.

Older saved simulations are rebuilt into the v8 PDF layout when opened. Records saved before both strategy schedules existed fall back safely to the legacy not-rebalanced schedule.

## QA
- Full automated suite: 178 passed.
- Sample PDF generated and rendered successfully.
- Pages 3-5 visually inspected for clipping, overlap, and readability.
