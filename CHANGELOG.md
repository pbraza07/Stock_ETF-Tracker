# MarketScope Changelog

## 5.11.1 - 2026-09-04

- Added the top-level **Favorite Picks** workspace and its **Pick Fav** action without moving or removing existing MarketScope tabs.
- Added an evidence-backed stock-only screen across the currently loaded MarketScope universe. It excludes ETFs and unclassified or insufficient-history securities, then retains a diverse finalist set within every eligible sector.
- Reused the Future Projection model stack for finalists: expected-return shrinkage, current Bear/Normal/Bull starting probabilities, live valuation and fundamental conditioning, adaptive volatility/correlation, Student-t shocks, historical block bootstrap, Factor/CMA cross-check, and no-look-ahead walk-forward ensemble weights.
- Added deterministic five-year P10, P25, P50, P75, and P90 CAGR estimates in ascending order. The ranking favors downside resilience and calibrated central outcomes instead of selecting the largest upside forecast.
- Added a Top 2 table for each eligible stock sector with score, sector rank, current/historical facts, modeled risk, confidence, data date, plain-language selection evidence, and key-risk explanations.
- Added current-market regime cards, data-freshness/fallback warnings, methodology and ensemble-weight disclosure, and a downloadable Favorite Picks CSV.
- Added responsive layouts that grow and wrap on desktop/mobile instead of clipping ranking facts.
- Added Favorite Picks regression coverage for stock eligibility, Top 2 enforcement, deterministic output, governed percentile ordering, live conditioning, historical fallback, evidence fields, and one-stock sector handling.

## 5.11.0 - 2026-09-04

- Rebuilt Future Projection from the preserved v5.10.1 baseline while leaving every historical simulator calculation and tab unchanged.
- Replaced the four-slot holding form with one searchable, duplicate-safe stock/ETF selector that accepts one or any larger number of holdings from the current MarketScope universe.
- Added dynamic equal weighting, scalable custom-allocation controls, unlimited simulator handoff, and responsive holding/result cards that grow instead of clipping long values.
- Added a user-selectable Projection Start Year whose default remains the year after the latest completed historical year and whose dashboard/forecast labels update dynamically.
- Standardized all Future Projection percentile outputs and graphs to P10, P25, P50, P75, and P90 in ascending order; added individual, distinctly colored graph toggles and six graph views.
- Added a live/recent Market State using Yahoo/yfinance price, adjusted-history, volatility, breadth, trend, valuation, fundamental, and bounded analyst inputs plus official macro series retrieved through FRED.
- Conditioned the existing Bear/Normal/Bull first-state probabilities, expected returns, volatility, and correlations while preserving Markov transitions, Student-t shocks, covariance shrinkage, cash flows, depletion logic, and deterministic seeds.
- Added AUTO, Conservative, Balanced, Growth, and Stress Test projection profiles. Growth does not inflate expected returns; Stress Test increases Bear persistence, volatility, and correlations.
- Added a three-model ensemble: primary Adaptive Regime Monte Carlo, contiguous Historical Block Bootstrap, and Factor/CMA validation model, with weights set by no-look-ahead walk-forward calibration.
- Added a 0-100 Projection Calibration Score, confidence explanation, current-market dashboard, portfolio concentration diagnostics, data-freshness panel, explicit cached/historical fallbacks, and complete projection audit record.
- Expanded Excel/PDF exports with live market state, freshness, model calibration, walk-forward observations, model comparison, and audit data.
- Added v5.11.0 adaptive-projection regression coverage; the full 518-test suite passes.

## 5.10.1 — 2026-09-03

- Fixed `KeyError: ''` when Future Projection opened with its four default empty holding fields.
- Restricted historical-data lookups to four nonempty, unique tickers that exist in the current MarketScope universe.
- Removed the incorrect duplicate-ticker warning for blank or partially completed portfolios.
- Added regression coverage for empty and partially completed holding selections.

## 5.10.0 — 2026-09-03

- Added the top-level Future Projection workspace beside the existing simulators.
- Added dynamic four-holding stock/ETF selection, equal/custom allocation, simulator/ranked-portfolio handoff, and responsive validation.
- Added reproducible 5,000/20,000/50,000-path correlated Monte Carlo projections with Bear/Normal/Bull transitions, Student-t shocks, covariance shrinkage, and governed capital-market assumptions.
- Added actual-monthly modeling with explicit, labeled proxy imputation for missing history and per-holding confidence diagnostics.
- Added rebalanced, non-rebalanced, and side-by-side cash-flow paths with beginning/end timing, inflation, contributions, fees, pro-rata withdrawals, shortfalls, and exact depletion dates.
- Added summary cards, synchronized interactive probability charts, annual/monthly result tables, and holding-level details.
- Added high-resolution PDF, multi-sheet Excel, and precision CSV exports.
- Added in-session result caching, background calculation progress, deterministic seeds, and mobile layouts.
- Added 20 Future Projection acceptance/regression tests. Existing historical simulator calculations and withdrawal tabs are unchanged.

## 5.9.82 — 2026-09-03

- Added every annual rolling cohort's initiation and depletion outcome inside the annual depletion cards.
- Removed the obsolete captions beneath those bordered cards.
