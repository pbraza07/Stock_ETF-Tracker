# MarketScope v5.11.22

Fixes the opaque unavailable-data experience introduced in v5.11.21.

- Official FRED observations API when FRED_API_KEY is configured; retains exact USPHCI/SAHMREALTIME data and native charts.
- Safe connection errors and configuration guidance, with no credentials in displayed errors or stored source URLs.
- Optional Trading Economics API calendar, explicitly selected and labeled separately from the default Investing.com collector.
- Validated last-good GitHub snapshots, collection workflow every six hours/manual, and preservation of previous files on failure.
- No changes to portfolio simulation, ranking, or projection calculations.

Read MACRO_DATA_SETUP.md before deployment. This is not a zero-configuration guarantee: API access requires credentials, Investing.com has no public API, and a saved snapshot exists only after successful collection. No authenticated provider API request or live Render deployment was verified in this session. Local direct-provider checks were interrupted by network approval cancellation; that does not establish the cause of the user's Render failure.

All 606 regression tests passed. Regression validation includes FRED API parsing, secret redaction, snapshot recovery, failed-refresh preservation, and optional calendar filtering. GitHub/Render are not modified by this release package.
