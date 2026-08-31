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


## v5.9.45
- Added Top 100 Rebalanced Monthly and Not Rebalanced Monthly 10Y presets ($300K start / $5K monthly / HWM excluded / four different sectors).
- Renamed annual withdrawal UI to Yearly withdrawal and added mutually exclusive Monthly withdrawal controls.
- Portfolio PDFs now include full month-by-month strategy results when monthly withdrawal mode is saved.
- PDF layout contract upgraded to v9; saved-PDF persistence protections remain unchanged.
