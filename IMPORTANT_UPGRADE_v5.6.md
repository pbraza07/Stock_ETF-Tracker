# MarketScope v5.6 upgrade

This package changes the card navigator so every card shows the complete 1D-to-10Y performance ladder and can be sorted by every displayed return horizon or analyst rating.

The package also adopts the supplied CSV universe containing exactly **213 ETFs**. The generated universe, bootstrap universe and `data/etf_allowlist.csv` are aligned to those 213 ETF symbols.

After deployment, run the GitHub Action once so the durable snapshot is refreshed with the latest Nasdaq >$100B stock universe plus the 213-ETF list. Existing persistent return rows are preserved when a refresh source temporarily fails.
