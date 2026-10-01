# MarketScope v5.9.2 — ETF Holdings + Bottom Pagination

## New
- Every ETF card now includes an on-demand **Holdings** button.
- Holdings come from Yahoo Finance through yfinance `Ticker.funds_data.top_holdings`.
- MarketScope displays **Top 10** when 10 rows are returned; if Yahoo returns fewer than 10 but at least 5, MarketScope displays **Top 5**. If fewer than five are available, only the returned rows are shown and nothing is fabricated.
- Holdings requests run only after the button is clicked and are cached for six hours, protecting dashboard startup speed.
- A second Previous / Next pagination control is now placed at the bottom of the card grid for easier mobile and desktop navigation.

## Preserved
- 213-ETF CSV universe
- Nasdaq stocks strictly above $100B
- News, live intraday chart, analyst price targets, annual returns, investment simulator, buy signals, and sorting
