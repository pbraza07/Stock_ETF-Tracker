# MarketScope Data Source Notice — v5.4

## Automatic stock universe

MarketScope retrieves stock listings directly from the public Nasdaq Stock Screener response and keeps only rows whose reported market capitalization is **strictly greater than $100,000,000,000 ($100B)**. The v5.4 automatic universe does not use the prior unofficial mirror fallback.

## ETFs

The 213-ETF CSV allowlist remains tracked separately from the stock market-cap screen.

## Analyst ratings

Stock analyst consensus is sourced from Nasdaq Stock Screener recommendation buckets where available. ETFs are shown as Not Rated unless Nasdaq itself exposes a genuine analyst/recommendation field for the fund.

## Return data

Historical return calculations use adjusted Yahoo Finance/yfinance market history. Stocks do not have NAV. ETF NAV is displayed separately when available and should not be confused with market-price total return.

Free public data can be delayed, unavailable, revised, rate-limited, or subject to source terms. Verify execution-critical prices with your broker and fund NAV figures with the fund issuer.


## v5.8 News Impact
Recent card news is retrieved on demand through Yahoo Finance via yfinance. Direction arrows are rule-based interpretations of fundamental headline/summary language and are not guaranteed forecasts. Neutral/ambiguous stories are omitted from directional display.
