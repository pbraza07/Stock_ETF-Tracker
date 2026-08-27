# MarketScope Data Source Notice

MarketScope is designed for personal/research use without a paid market-data API key.

## Universe source

The stock universe is rebuilt from the **Nasdaq Stock Screener** and filtered to rows with market capitalization strictly greater than **$100,000,000**. If the direct Nasdaq request is temporarily unavailable, the updater can use a public daily-refreshed GitHub mirror generated from the Nasdaq screener data.

The user-requested ETF symbols are maintained separately in `data/etf_allowlist.csv` and merged into the universe regardless of ETF market capitalization.

## Price / return source

Yahoo Finance market history is accessed through the open-source `yfinance` package. No paid market-data API key is required. Historical calculations use adjusted daily history.

Free website data may be delayed, incomplete, corrected later, or temporarily rate-limited. Order-critical prices should be verified with the user's broker. ETF NAV should be verified with the fund sponsor when exact NAV is material.
