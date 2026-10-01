# MarketScope 5.11.49 — News navigation and manual refresh

- Market News is the first main tab; Alerts & Help is always last in both normal navigation and Future Projection focus mode.
- The top-of-tab button now reads “Pull all 13 news feeds now.” Each manual request fetches all configured feeds regardless of the automatic freshness interval. The simultaneous-refresh lock remains in place.
- Automatic 15-minute checks while the tab is open and the hourly GitHub collector remain available. Gathered stories still save into the existing archive, with per-source health reporting and progress.

Validation: 32 targeted news and navigation tests passed, with 5 existing dependency warnings. Tests verify the tab-to-content mapping in both navigation branches and two consecutive manual pulls, each attempting all 13 feeds. Network calls were mocked for these tests; live publisher delivery and production deployment were not verified. No portfolio or projection calculations were changed.
