# MarketScope v5.11.0 - Live Adaptive Future Projection

Install this release over the current repository after preserving v5.10.1 as the rollback package.

## What changed

- One searchable Future Projection selector now accepts one or any larger number of current-universe stocks/ETFs.
- Projection Start Year is user-selectable and defaults dynamically to the first year after completed history.
- Future Projection uses only P10/P25/P50/P75/P90 outputs, with ascending tables and distinct graph toggles.
- Recent Yahoo/yfinance market/fundamental data and official FRED macro series condition the existing Monte Carlo engine.
- Dynamic first-state regime probabilities feed the preserved Bear/Normal/Bull Markov process.
- Recent volatility and correlations modify risk assumptions within governed safety bounds.
- Walk-forward validation weights Adaptive Monte Carlo, Historical Block Bootstrap, and Factor/CMA distributions.
- Current-market, freshness, calibration, concentration-risk, and audit panels are included in the UI and exports.

## Deployment

No new environment variables or migrations are required. Keep the existing GitHub token/repository/branch settings. Upload over the repository rather than deleting it so live saved simulations and generated PDFs remain intact.

## Verification

Run `python -m pytest -q`. The v5.11.0 package passes 518 tests. Then run Streamlit and verify `/_stcore/health`, one-holding and multi-holding projections, current-data fallback labeling, the five percentile toggles, and Excel/CSV/PDF downloads.
