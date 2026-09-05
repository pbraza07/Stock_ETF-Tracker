# MarketScope v5.11.1 Upgrade Notes

## Deploy the files at the repository root

The release ZIP is intentionally packaged without an enclosing directory. After extraction, these files must be at the GitHub repository root:

- `app.py`
- `favorite_picks.py`
- `requirements.txt`
- `render.yaml`
- `Procfile`
- `VERSION.txt`

Do not upload the release into `data/`. Render runs the build command from its configured root and cannot locate `requirements.txt` when the application is nested unexpectedly.

For the repository-root layout, leave Render's **Root Directory** blank. The existing build/start commands and environment variables remain valid.

## Preserve live user data

Upload this release over the existing repository and preserve:

- `data/saved_portfolio_simulations.json`
- `data/generated_pdfs/`
- `static/generated_pdfs/`

## Validate after deployment

1. Confirm the header displays v5.11.1.
2. Open **Favorite Picks** and select **Pick Fav**.
3. Confirm each eligible sector shows no more than two stock picks.
4. Confirm P10, P25, P50, P75, and P90 appear in ascending order.
5. Confirm each row includes **Why Selected**, **Key Risk**, confidence, and data-as-of information.
6. Open **Future Projection** and run a fixed-seed smoke test.
7. Open **Portfolio Simulator** and confirm the existing withdrawal tabs are unchanged.

Favorite Picks is a probabilistic research screen, not a guarantee or individualized investment advice.
