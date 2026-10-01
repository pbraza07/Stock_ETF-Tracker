# MarketScope v5.9.58 — Dynamic Lifetime Annual History

MarketScope no longer has a hard-coded 25-year ceiling.

## Automatic annual expansion

The tracked annual-history baseline remains calendar year **2001**. The newest annual column is always the latest completed calendar year.

Therefore:

- during 2026: 25 completed years = 2001–2025
- during 2027: 26 completed years = 2001–2026
- during 2028: 27 completed years = 2001–2027
- every later year: one additional completed annual-return column is added automatically

No code edit or version release is required for the extra year.

The runtime derives the horizon from:

`latest completed year - 2001 + 1`

and builds the year labels dynamically.

## App-wide behavior

The dynamic completed-year count is used by:

- Market Navigator Card View
- Market Table
- Investment Simulator
- Portfolio Simulator
- yearly withdrawals
- monthly withdrawals
- Portfolio common-history logic
- Stock & ETF Comparison
- Sector Performance
- Worst Year
- historical year charts
- saved Portfolio PDF rebuilds
- scheduled snapshot refresh
- Stooq historical verification
- annual/monthly reconciliation validation

The maximum horizon selector automatically grows. For example, the current 1Y–25Y control becomes 1Y–26Y after 2026 completes.

## Dynamic monthly source

`data/monthly_returns_full_history.csv` replaces the old horizon-specific monthly filename as the durable full-history withdrawal source.

It contains genuine adjusted month-end returns for every tracked completed year from 2001 through the latest completed year.

The existing `monthly_returns_10y.csv` remains intentionally limited to the latest 10 completed years for the specialized Top 100 monthly-withdrawal ranking product.

The legacy `monthly_returns_25y.csv` is accepted as an upgrade fallback but is no longer the future-proof persistence target.

## Annual aggregation

On each normal scheduled refresh MarketScope:

1. determines the latest completed calendar year;
2. constructs every annual column from that year back through 2001;
3. downloads adjusted daily history from the 2000 anchor;
4. calculates the new year's genuine annual return;
5. preserves prior verified years;
6. writes the dynamically expanded market snapshot;
7. writes matching actual monthly history;
8. reconciles each complete 12-month path to its annual Market Table return;
9. cross-checks annual returns against Stooq when comparable data are available;
10. persists everything through the race-safe GitHub mechanism.

## PDFs

Portfolio PDF layout is upgraded to **v17**.

Combined annual-return pages now paginate dynamically. The PDF no longer assumes 25 annual columns. When the history grows beyond the space available on one page, earlier years automatically continue on additional pages.

Annual withdrawal schedules already paginate and therefore also grow with the annual-history horizon.

## Fixed-horizon ranking products

The 5Y and 10Y product names remain fixed horizons by design, but their calendar windows now roll automatically.

`scripts/build_dynamic_annual_rankings.py` checks whether the annual ranking files already contain the latest completed year. On normal daily refreshes it exits immediately when they are current. After a new calendar year completes, it automatically rebuilds:

- 5Y Top 200 Best Profit
- 5Y Top 200 Best Worst Year
- 10Y Top 200 Best Profit
- 10Y Top 200 Best Worst Year
- 10Y Rebalanced annual-withdrawal Top 100
- 10Y Not-Rebalanced annual-withdrawal Top 100

The 10Y actual-monthly ranking already selects the latest ten complete years from the monthly source, and the recession-balanced ranking now uses the latest ten completed annual years for its growth window.

So the full history grows from 25Y to 26Y to 27Y, while fixed-horizon ranking products stay 5Y/10Y but automatically roll forward one calendar year.
