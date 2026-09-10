# MarketScope v5.11.23 — Updated recession chart series

The Recession Indicators tab now displays:
1. USPHCI — Coincident Economic Activity Index for the United States (index, 2007=100; seasonally adjusted).
2. RECPROUSM156N — Smoothed U.S. Recession Probabilities (percent; not seasonally adjusted), replacing SAHMREALTIME.

Both official API requests use realtime_start=1990-07-04 and realtime_end=9999-12-31 as requested, with file_type=json. The API key comes from FRED_API_KEY; credentials are not included in this release. Set FRED_API_KEY in Render Environment and GitHub Actions secrets, then run Refresh macro snapshots. Existing keys already configured under that name continue to work.

Real-time parameters select data vintages, not observation dates. Multiple revisions for a month are sorted by vintage and only the latest returned revision is displayed. Incomplete responses are rejected instead of charting partial history.

The probability chart uses a 0–100% axis and percentage hover/summary labels; 0.76 remains 0.76%, not 76%. No Sahm threshold or triggered/not-triggered status remains on that chart. The explanation identifies smoothed, revisable estimates of recession conditions in the observation month, not a forward recession forecast.

Snapshot collection now requests RECPROUSM156N. Older Sahm snapshots are preserved but are not used for these charts. Calendar, portfolio calculations and PDF exports are unchanged.

Sources:
- https://fred.stlouisfed.org/series/USPHCI
- https://fred.stlouisfed.org/series/RECPROUSM156N
- https://fred.stlouisfed.org/docs/api/fred/series_observations.html

The release is not deployed. Authenticated live provider access and the Render environment remain unverified; the key is not configured remotely by creating this ZIP.
