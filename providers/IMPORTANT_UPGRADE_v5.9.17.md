# IMPORTANT — First refresh after v5.9.17

After deploying v5.9.17, run the MarketScope GitHub snapshot refresh once. Older durable snapshots only contain the prior 10 annual-return columns. The refreshed snapshot adds the additional completed-year columns (2015 through 2006 during 2026) wherever Yahoo adjusted history is available.

Newer stocks/ETFs will correctly show unavailable values for years before inception; MarketScope does not fabricate those returns.
