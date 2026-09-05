# MarketScope v5.11.2 Upgrade Notes

## Preserve the permanent history files

Upload this release over the existing GitHub repository. Do not delete or replace these live files:

- `data/favorite_picks_history.json`
- `data/universe_change_history.json`
- `data/saved_portfolio_simulations.json`
- `data/generated_pdfs/`
- `static/generated_pdfs/`

The v5.11.2 package includes `data/favorite_picks_history.bootstrap.json`, not the live Favorite Picks ledger. This protects all prior runs and first-detected timestamps during upgrades.

## Required placement

Place `app.py`, `favorite_picks.py`, `favorite_picks_history.py`, `requirements.txt`, `render.yaml`, and `Procfile` at the repository root. Leave Render's **Root Directory** blank.

## Existing environment setting

No new environment-variable name is required. Verify the existing `MARKETSCOPE_GITHUB_TOKEN` has repository Contents read/write permission. Without it, manual Pick Fav runs remain on the current Render instance only; the scheduled GitHub workflow still creates the daily durable ledger.

## Verification

1. Confirm the application displays v5.11.2.
2. Run **Pick Fav** and review the Risk Rating and Risk Score columns.
3. Run it again without changing the data; no duplicate change event should appear.
4. Review Favorite Picks → **Pick Fav Change Trail**.
5. Review Market Navigator → **Pick Fav Change Trail**.
6. Verify replacement events display both the dropped stock and new stock.
7. Verify First Detected timestamps do not change on later runs.

Favorite Picks remains a probabilistic research screen, not a guarantee or individualized investment advice.
