# MarketScope v5.10.0 — Future Projection

This release adds a complete probabilistic Future Projection workspace while preserving every existing MarketScope tab, ranking, historical calculation, and saved-simulation contract.

## New capability

- Four searchable stocks/ETFs loaded dynamically from the current MarketScope universe.
- Equal or exact custom allocation; simulator and ranked-portfolio handoff.
- Yearly, actual-monthly, beginning-period, and end-period withdrawals.
- Rebalanced, non-rebalanced, and side-by-side strategies with yearly, quarterly, or monthly rebalancing.
- Standard (5,000), Advanced (20,000), and High Precision (50,000) deterministic simulations.
- Regime-aware correlated Student-t return paths using separately governed capital-market assumptions.
- Explicit limited-history blending, observed/imputed period counts, affected tickers, and model confidence.
- Sequential balances, proportional withdrawals, contributions, fees, shortfalls, and exact depletion year/month.
- Responsive summary cards, synchronized chart/table data, probability bands, no-withdrawal comparison, and holding detail.
- Excel, CSV, and high-resolution PDF downloads.

## Files added

- `future_projection.py` — validation, calibration, simulation, result frames, and exports.
- `future_projection_config.py` — governed capital-market and regime assumptions.
- `future_projection_ui.py` — Streamlit inputs, worker progress, cache, chart, tables, and downloads.
- `tests/test_v510_future_projection.py` — the 20 required acceptance cases.
- `CHANGELOG.md` — release history.

## Files updated

- `app.py` — Future Projection tab, portfolio handoff actions, and projection-only partial monthly-history loader.
- `styles.css` — responsive projection layouts and state styling.
- `requirements.txt` — Plotly and OpenPyXL dependencies.
- `README.md`, `DEPLOY_GITHUB_RENDER.md`, `FINAL_DEPLOYMENT_NOTES.md`, `VERSION.txt`, and the refresh-workflow display name.

## Deployment

Upload the release contents over the current GitHub repository and push to `main`. Do not delete or overwrite live `data/saved_portfolio_simulations.json`, `data/generated_pdfs/`, or `static/generated_pdfs/` paths. Render uses the existing `render.yaml`; no environment-variable changes or data migration are required.

The first normal Render build installs Plotly and OpenPyXL. Run the existing refresh workflow only if MarketScope's annual or monthly historical files are stale.
