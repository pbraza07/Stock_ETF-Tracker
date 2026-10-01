# MarketScope 5.11.16 — cumulative update

Includes the v5.11.15 YTD progress, PDF/Excel reports, profit graphs and saved portfolio summary/share/delete controls.

- Main dashboard now embeds Investing.com's official weekly economic calendar with importance=3 only, announcement times, Eastern Time default and timezone control. The third-party widget loads directly in the browser, with a source link if browser restrictions block it. No copied or fabricated event list is shipped.
- Withdrawal / rebalance cadence includes None. This disables both withdrawals and rebalancing, even if a previously entered withdrawal remains in the form.
- Simulation start defaults to YTD. Choose Custom date to select earlier dates. Data is requested from before the chosen start; all holdings must share real observations. Reports and saved records preserve requested/actual dates and disclose partial coverage.
- The two stock rankings now select five eligible stocks per sector using their existing resilience/max-profit scores and anti-churn preference. Fewer eligible stocks produce fewer selections for that sector. These are relative rankings, not new absolute pass/fail investment criteria.
- Tables display actual total stocks/sectors. Buttons, exports and portfolio controls use Top 5 per Sector / Sector-Leader names. Existing history filenames remain stable to preserve deployed data; new runs carry the new selection policy. Old Top 12 runs remain in history but are not presented as the new lists. First click rebuilds a sector list if none is saved.
- Historical studies use the new selection rule but retain their previously disclosed point-in-time data limitations.

Deploy the repository-root ZIP contents while preserving live data. No additional environment variables. Not deployed to GitHub or Render by this update.

Calendar configuration source: https://www.investing.com/webmaster-tools/economiccalendar
