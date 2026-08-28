# MarketScope v5.9.13 — Card Render + Sidebar Removal

- Removed the entire sidebar shown in the supplied screenshot: Market controls, Reload server snapshot, persistence warning/status, and Find any stock or ETF/add-symbol form.
- Fixed Card View showing a result count but no cards.
- Root cause: the v5.9.10 profit-period fragment was accidentally dedented out of the Card View tab, causing card helper/rendering code to be nested inside the fragment instead of executing normally.
- Restored Card View card grid, click-to-project return controls, action buttons, news/holdings, bottom pagination, and instrument detail execution.
- Added a real zero-match message for Card View.
- Treats a deselected Instrument segmented control as All.
- Keeps searchable Card View and Table View fields.
