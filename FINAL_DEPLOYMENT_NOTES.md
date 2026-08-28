# MarketScope v5.7 Final Deployment Notes

## Main changes

- Long-horizon card metrics are now actual completed calendar-year returns rather than CAGR.
- The ten year labels roll automatically. During 2026 they are 2025 through 2016.
- Cards remain sortable by every displayed return and analyst rating.
- Added a dollar Investment Simulator that compounds the actual annual returns and, optionally, current YTD.
- Selected-instrument detail view shows estimated historical ending value, profit/loss, and total compounded return.
- The preserved ETF universe remains exactly 213 symbols.
- Daily scheduled refresh remains 6:00 PM U.S. Eastern.
- Snapshot history period is now `max` so the oldest required year-end anchor is available.

## After upload

Run the v5.7 GitHub Action once before judging the annual-year cells. Legacy CAGR values are intentionally not renamed or reused as calendar-year returns.
