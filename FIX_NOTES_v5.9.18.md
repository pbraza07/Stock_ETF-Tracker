# MarketScope v5.9.18

- Adds a visible Nasdaq universe audit strip with the last screening refresh timestamp and stocks added/removed at the latest >$100B refresh.
- Persists `data/universe_metadata.json` from the scheduled GitHub Action so membership changes remain auditable across Render redeploys.
- Adds a compact 2-year adjusted daily-price chart to each visible Stock/ETF card, using one batched Yahoo Finance request per card page and a 30-minute cache.
- Restores the compact v5.9.7 mobile card layout: return/profit tiles remain three columns instead of stacking vertically.
- Keeps every return tile clickable with the existing card-local exact-period profit calculation.
- Changes Portfolio Split Simulator default total investment from $200,000 to $100,000.
- Saved portfolio simulations now retain instrument name, sector, analyst rating, and analyst low/average/high price targets.
- PDF page 1 now includes a portfolio instrument snapshot with symbol/name, sector, analyst rating, and low/average/high price targets. Combined timeframe performance is preserved on page 2 for readability.
