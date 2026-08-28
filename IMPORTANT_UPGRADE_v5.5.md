# MarketScope v5.5 Upgrade Notes

## New instrument-card navigation
The primary stock/ETF spreadsheet table has been replaced by a responsive card navigator. Each instrument is a clickable card/button. Open a card to see its full performance matrix, analyst rating, buy signals, sector and chart controls.

## New annualized return horizons
The daily and manual historical refresh now calculates annualized CAGR for every whole-year horizon from 1Y through 10Y:

1Y Avg, 2Y Avg, 3Y Avg, 4Y Avg, 5Y Avg, 6Y Avg, 7Y Avg, 8Y Avg, 9Y Avg, 10Y Avg.

Short windows remain point-to-point adjusted total return: 1D, 1M, 3M, 6M and YTD.

## First deployment
After uploading v5.5, run the GitHub Action once so the newly added 2Y/4Y/6Y/7Y/8Y/9Y fields are populated in the durable snapshot immediately. Existing saved data is preserved; missing new horizon fields remain blank until refreshed.

## Existing rules preserved
- Nasdaq Stock Screener automatic stock universe: market cap strictly greater than $100B.
- Requested ETF allowlist remains included.
- 6:00 PM America/New_York daily refresh remains unchanged.
- Manual refresh progress/counter remains enabled.
- Nasdaq analyst rating colors and buy-signal logic remain enabled.
- GitHub remains the durable snapshot source of truth.
