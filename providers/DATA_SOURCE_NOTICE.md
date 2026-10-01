# Data Source Notice — v5.9.55

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

## Independent annual-return verification — v5.9.56

Primary annual-return data: Yahoo Finance / yfinance adjusted historical prices.

Independent cross-check: Stooq U.S. bulk historical Close dataset (`https://static.stooq.com/db/h/d_us_txt.zip`), downloaded automatically by the GitHub refresh and cached weekly.

The Stooq data is used only to compare annual returns. It never replaces the primary Yahoo/yfinance value automatically. MarketScope flags differences above 0.25 percentage points as `Review`.

## v5.9.57 withdrawal source alignment

Annual withdrawals use the exact completed annual-return columns displayed in Market Table.

Monthly withdrawals use `data/monthly_returns_25y.csv`, generated from the same Yahoo/yfinance adjusted daily price history. The monthly path is not derived from annual returns. Each complete 12-month set is compounded and reconciled to the corresponding Market Table annual return before the data is persisted.

## v5.9.58 dynamic history window

Yahoo/yfinance remains the primary adjusted-price source. The oldest tracked completed annual return remains 2001, requiring the 2000 year-end anchor. The newest tracked annual year is derived automatically as the latest completed calendar year, so no source configuration change is required when a new year closes.

The durable full-history monthly source is now `data/monthly_returns_full_history.csv`.

## v5.9.61 $160K withdrawal ranking source

The new $300K / $160K-per-year Top-100 ranking family is generated from the committed annual-performance CSV snapshot in `data/annual_performance_160k_source.csv`.

Only completed calendar-year stock returns are used for the ten-year ranking. The generator requires complete data for all ten ranking years, four different sectors per portfolio, and a maximum of five Top-100 appearances per ticker.
## v5.9.63 20Y $160K Top 250 ranking source

The new 20-year high-withdrawal ranking family uses the frozen annual-performance source saved as `data/annual_performance_20y_160k_source.csv`. It contains the 20 completed calendar-year return columns from 2006 through 2025 used by this release.

Only stocks with complete data for all 20 years are eligible. The ranking generator evaluates four-stock portfolios with four different sectors, applies a $160,000 withdrawal after each year's return, and caps each ticker at ten appearances across each Top 250 list.
## v5.9.64 analyst price targets

Stock analyst Low, Average/Consensus, and High targets come from Yahoo Finance through yfinance (`analyst_price_targets`, with Yahoo quote metadata fallback). Durable snapshot values are preferred; missing or partial stock target ranges are hydrated lazily in the app. ETFs remain blank when stock-style consensus targets are not published.

## v5.9.66 analyst target source

Stock analyst Low / Average / High targets are sourced from Yahoo Finance through yfinance's analyst-price-target and financial-data interfaces. MarketScope first preserves durable saved targets, then retries current Yahoo consensus data when a range is missing or incomplete.

`Price Target Source` and `Price Target Updated ET` are retained in the snapshot and exposed in Market Table / Comparison Table. ETF stock-style analyst targets remain blank when Yahoo does not publish them.

## v5.9.68 Market Table-to-PDF target transcription

When Market Table has already resolved valid stock analyst Low / Average / High values, MarketScope keeps those exact values in an in-session target registry. Portfolio PDF page 1 overlays this registry before any new Yahoo request, so a target visible in Market Table cannot disappear from the PDF merely because a second provider request is throttled or empty.

## v5.9.70 Nasdaq change-history source

`data/universe_change_history.json` is generated from the same Nasdaq Stock Screener universe refresh that maintains the >$100B stock universe and Nasdaq analyst-consensus ratings.

The log records actual refresh-to-refresh changes only:
- stock entered the tracked >$100B universe
- stock exited the tracked >$100B universe
- analyst consensus rating changed

The historical file is append-only. The Market Navigator's 6-month display filter does not delete older events.
