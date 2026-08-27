# MarketScope Data Sources

## Universe and stock analyst ratings

Primary source: Nasdaq Stock Screener public endpoint.

MarketScope keeps stock rows with market capitalization strictly greater than $100,000,000 and excludes obvious warrants, rights, certain notes, and preferred securities. Analyst ratings use Nasdaq screener recommendation buckets: Strong Buy, Buy, Hold, Sell, Strong Sell.

## ETFs

The requested ETF list is stored in `data/etf_allowlist.csv`. Nasdaq's public ETF screener does not expose the same stock-style analyst-consensus filter. MarketScope only uses an ETF analyst rating when Nasdaq actually returns a genuine analyst/recommendation field; otherwise it displays Not Rated.

## Price / return history

Yahoo Finance data is accessed through yfinance for adjusted market-price history and live/manual price refreshes. No paid market-data API key is required.

Free website data can be delayed, corrected, unavailable, or rate-limited. Verify order-critical prices with a broker and ETF NAV with the fund issuer.
