# MarketScope 5.11.9 — Top 12 dedicated table fix

This release replaces the Top 12 asynchronous polling interface with a direct,
deterministic click-to-table flow.

- The Recession-Resilient button opens a dedicated 12-row Recession table.
- The Max-Profit button opens a separate dedicated 12-row Max-Profit table.
- The former shared ranking-view radio control has been removed.
- A button request remains in session state until the calculation consumes it.
- The table is produced during the same Streamlit run that performs the ranking.
- Remote ranking-history reads cannot delay the calculation; prior local history
  is used for the stability threshold and durable history sync remains background work.
- Full-universe live downloads cannot delay the table. The loaded MarketScope
  snapshot supplies current price, market cap, sector, industry and recent
  relative strength. The report discloses when supplemental daily/live evidence
  is unavailable.
- Tables use the requested labels and keep Rank and Ticker pinned where supported.
- The scoring engine, Future Projection engine and historical simulators are unchanged.

The full MarketScope data fixture evaluated 167 eligible stocks from 387 rows,
selected exactly 12 stocks for each ranking, and never exceeded four stocks in a
sector. Automated UI tests click each button, verify the correct independent
12-row table, switch between the two tables, and verify persistence after reruns.

Certified point-in-time backtesting remains unavailable because the recovered
datasets do not contain historical universe membership and historical sector
classification snapshots. The app labels that historical study exploratory and
does not claim it is free of survivorship/classification bias.

Deploy the extracted contents at the repository root, preserve existing server
data, redeploy, and confirm version 5.11.9. No new environment variables or
dependencies are required.
