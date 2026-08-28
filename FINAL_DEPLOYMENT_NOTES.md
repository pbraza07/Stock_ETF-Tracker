# Final Deployment Notes — MarketScope v5.9.1

- Nasdaq automatic stock universe: market cap strictly >$100B
- ETF universe: exactly 213 CSV symbols
- Live opened-instrument chart: Yahoo/yfinance, 1-minute bars when available, ~60-second auto refresh
- Live chart fallback: 5-minute Yahoo bars when 1-minute data is unavailable
- Stock cards: Yahoo analyst Price Target Low / Average / High
- ETFs: no fabricated stock-style analyst price targets
- Price targets: scheduled/manual refresh + upgrade-safe lazy visible-card fallback
- Calendar-year returns: actual annual adjusted returns, not CAGR
- Investment horizon: selectable 1Y–10Y
- Total Profit ($) sort respects selected investment horizon
- News Impact: on-demand recent directional fundamental headlines
- Historical chart: current year + prior 10 calendar years
- Daily scheduled refresh: 6:00 PM U.S. Eastern

## v5.9.1
Fixes ETF card HTML rendering and adds stock sector labels beneath stock names. No data refresh is required solely for this UI patch; a normal Render redeploy is sufficient.


## v5.9.2
Upload this release over the existing repository. No market snapshot reset is required. ETF holdings are retrieved on demand and do not need a scheduled refresh. Bottom card pagination is UI-only.


## v5.9.3 — Profit & portfolio simulation
- Return tiles in each card are clickable for exact-period dollar profit calculations.
- YTD is available as a standalone investment period.
- Portfolio Split Simulator defaults to $200,000 and supports equal or custom percentage splits across multiple stocks/ETFs, with YTD or 1Y–10Y historical horizons.

## v5.9.4 — Card / Table tabs
Upload the release over the current repository and let Render redeploy. No snapshot reset is required. Table View reads the same persisted snapshot as Card View.
