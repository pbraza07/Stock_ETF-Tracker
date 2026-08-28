# MarketScope Data Source Notice — v5.9.1

MarketScope uses free/public data paths and does not require a paid market-data API.

- **Nasdaq Stock Screener:** automatic stock universe (> $100B market cap) and stock consensus rating buckets.
- **Yahoo Finance through yfinance:** adjusted daily history, latest/intraday prices, the opened-instrument live chart, recent on-demand news, and stock analyst Low/Average/High price-target ranges when available.
- **ETF allowlist:** exactly 213 symbols stored in `data/etf_allowlist.csv`.

Yahoo and exchange delays, throttling, missing analyst coverage, and temporary source availability can occur. The live chart is near-real-time and is not an exchange-direct market feed. Price targets are analyst estimates and are not guaranteed outcomes.
