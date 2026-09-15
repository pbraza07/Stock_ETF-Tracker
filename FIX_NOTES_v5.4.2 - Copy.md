# MarketScope v5.4.2 — Sector, NAV & Readability Update

This build makes three UI-focused changes:

1. Sector filter pills are sourced only from rows where `Type == Stock`, so ETF-only category values do not appear as sector buttons.
2. The main table no longer includes the NAV column. NAV may remain in backend snapshots for compatibility, but it is not displayed or included in main-table filters.
3. Table readability is increased for desktop and mobile: 19px data cells, 21px bold symbols, 54px row height, larger headers, and a mobile CSS override that favors horizontal scrolling over tiny text.

All existing >$100B Nasdaq stock-universe logic, ETF allowlist, performance columns, buy signals, persistence, manual-refresh progress, and 6 PM Eastern daily schedule remain unchanged.
