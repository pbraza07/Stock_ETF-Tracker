# IMPORTANT UPGRADE v5.9.18

After deploying, run **Refresh MarketScope universe and snapshot** once in GitHub Actions. This creates and commits `data/universe_metadata.json` and populates the new Nasdaq refresh / added / removed status immediately.

Newly saved portfolio simulations capture analyst ratings and Low/Average/High price targets for PDF page 1. Older saved simulations may show `-` for target fields because those values were not stored in the older record.
