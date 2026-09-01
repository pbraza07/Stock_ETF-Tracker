# Data Source Notice — v5.9.54

Annual returns use Yahoo Finance/yfinance adjusted daily market history. The automatic refresh requests history from 2000-01-01 so the 25 completed calendar-year window has the prior-year anchor required for the oldest annual return. Values remain unavailable before genuine full-year price history exists. No annual return is synthesized.

# MarketScope Data Source Notice — v5.9.1

MarketScope uses free/public data paths and does not require a paid market-data API.

- **Nasdaq Stock Screener:** automatic stock universe (> $100B market cap) and stock consensus rating buckets.
- **Yahoo Finance through yfinance:** adjusted daily history, latest/intraday prices, the opened-instrument live chart, recent on-demand news, and stock analyst Low/Average/High price-target ranges when available.
- **ETF allowlist:** exactly 213 symbols stored in `data/etf_allowlist.csv`.

Yahoo and exchange delays, throttling, missing analyst coverage, and temporary source availability can occur. The live chart is near-real-time and is not an exchange-direct market feed. Price targets are analyst estimates and are not guaranteed outcomes.


## ETF holdings
ETF top holdings are retrieved on demand from Yahoo Finance through yfinance `Ticker.funds_data.top_holdings`. Availability and freshness vary by fund/provider.


## v5.9.6 portfolio income metrics
Portfolio regular-yield information is retrieved on demand from Yahoo Finance via yfinance for instruments included in a Portfolio Split simulation. MarketScope prefers trailing annual dividend/distribution rate divided by current price and may fall back to trailing 365-day cash dividends/distributions. Estimated annual dividend is allocated dollars multiplied by that trailing yield and is not a forecast.

## v5.9.18 card mini-chart and universe audit

Visible card charts use Yahoo Finance adjusted **1-day bars over the prior 2 years** through `yfinance`. The app batches only the currently visible card symbols and caches the result for 30 minutes.

`data/universe_metadata.json` is generated from each successful Nasdaq >$100B universe refresh and records the refresh timestamp plus symbols added/removed versus the prior automatic Nasdaq stock universe.


## v5.9.53 25-year annual history

The five oldest annual-return columns (2005-2001 during 2026) are populated only from genuine Yahoo/yfinance max adjusted-price history. MarketScope does not interpolate, extrapolate, copy adjacent years, or fabricate pre-inception returns. The bootstrap file contains the 25-year schema but may leave an older year blank until the durable history refresh succeeds for that instrument.
