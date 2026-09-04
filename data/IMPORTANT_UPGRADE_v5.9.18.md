# Important upgrade notes - v5.9.18

After deployment, run the **Refresh MarketScope universe and snapshot** GitHub Action once. This creates and commits `data/universe_metadata.json`, which powers the new Nasdaq Universe Last Refreshed and Stocks Added / Removed Today display.

The new card mini-charts use Yahoo Finance adjusted **1-day bars over 2 years**. They are loaded only for the visible card page and cached for 30 minutes to avoid a full-universe chart download.

Existing saved portfolio simulations remain readable. New simulations save analyst rating and price-target fields so the PDF first page can show them.
