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


## Universe audit metadata

MarketScope records the Nasdaq universe refresh time and the symbols added/removed during the current U.S. Eastern calendar day in `data/universe_metadata.json`. These changes are based on the app's Nasdaq >$100B stock rule.
