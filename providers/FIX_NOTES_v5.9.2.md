# MarketScope v5.9.2 Fix Notes

## ETF Top Holdings
- Added an ETF-only `Holdings` button inside each card.
- Holdings are fetched only when clicked from Yahoo Finance through yfinance `Ticker.funds_data.top_holdings`.
- Show Top 10 when 10 holdings are available.
- If fewer than 10 but at least 5 are returned, show Top 5.
- If Yahoo returns fewer than 5, show only what is available; never invent holdings.
- Holdings are cached for six hours to keep the card navigator fast.

## Bottom Pagination
- Added Previous / Next card pagination below the last row of cards.
- Existing top pagination remains available.
- Bottom pagination uses separate Streamlit keys and updates the same card page state.

## Preserved
- 213 ETFs from CSV universe
- Nasdaq stocks strictly above $100B
- Annual returns, investment simulator, news impact, live intraday chart, price targets, buy signals and card sorting
