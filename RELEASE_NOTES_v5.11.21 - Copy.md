# MarketScope v5.11.21 — Native recession indicators and economic calendar

Baseline: v5.11.20, matching the repository VERSION.txt checked during this update.

## Recession Indicators tab
- Adds a top-level Recession Indicators tab without removing or renaming existing tabs.
- Downloads USPHCI and SAHMREALTIME observations directly from FRED CSV endpoints and builds native Plotly charts using MarketScope's dark palette.
- Shows full series names, source attribution, units, latest observation month, retrieval timestamp, and chart interpretation.
- USPHCI: Coincident Economic Activity Index for the United States; index 2007=100, monthly, seasonally adjusted. Rising/falling activity is explained without inventing a recession cutoff.
- SAHMREALTIME: Real-time Sahm Rule Recession Indicator; monthly percentage points. Marks the 0.50 percentage-point threshold. Explains that this is not a probability or official recession declaration, and that real-time refers to information available in the historical month.
- Provides 5/10/20-year and full-history views, source observation tables, and CSV downloads. Missing monthly observations are chart gaps.
- Recession data downloads only when this tab is selected; the two series load concurrently. Valid downloads are reused for six hours, with manual refresh available.

## Native economic calendar
- Removes the Investing.com iframe and the cross-origin color-inversion workaround.
- Collects the public Investing.com weekly calendar response on the server, parses the data, and creates a native dark HTML table. No provider scripts or page markup are executed in the app.
- Independently enforces United States and exactly three-star importance on every event.
- Shows event date/name, announcement time, importance, actual, forecast, and previous; converts UTC timestamps to America/New_York with daylight-saving adjustment.
- Filters the week by Eastern dates, excluding prior-week cached events. Actual-value colors preserve Investing.com's assessment; higher numbers are not automatically treated as economically positive.
- Five-minute data cache with a manual refresh button. Refreshes occur on page interaction/rerun; this is not a streaming provider connection.

## Reliability and deployment
- Bounded HTTP connect/read timeouts, visible unavailable/stale messages, and last-valid data fallback. Retrieval timestamps are not represented as provider publication dates.
- Cache files live under data/macro_cache, excluded from release ZIPs. They survive process restarts if the filesystem persists; ephemeral Render disk content can be lost on redeploy.
- No new packages, API keys, or environment variables required. Provider availability and markup changes can affect collection; failures do not substitute fabricated events.
- Existing simulator calculations and projection/PDF exports are unchanged.
- Install extracted files at repository root, preserve live data, redeploy, and confirm version 5.11.21. GitHub/Render have not been updated by this task.

## Validation
- 600 regression tests passed, including six new recession/calendar tests and the updated native-calendar presentation contract.
- Initial direct HTTP requests returned 200 for both FRED CSV endpoints and the Investing.com weekly source. The captured calendar parsed 10 U.S. three-star events for the tested week.
- Later integrated live-download checks were interrupted by the environment's network approval cancellation. Live Render end-to-end collection is therefore still unverified.
- Streamlit AppTest verified both Plotly charts, threshold state, history selection, and native calendar rendering. The cloud browser blocked localhost preview (ERR_BLOCKED_BY_CLIENT), so desktop/mobile visual QA remains unverified.

Sources: https://fred.stlouisfed.org/series/USPHCI ; https://fred.stlouisfed.org/series/SAHMREALTIME ; https://www.investing.com/economic-calendar/
