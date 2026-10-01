# MarketScope 5.11.35 — Forward Planning research engine

This release adds an auditable forward financial-planning workflow. It is not a claim of certified forecast precision. The pre-change A-G review is in PLANNING_ARCHITECTURE.md; source/input contracts are in PLANNING_DATA.md.

## Delivered
- Forward Planning is the default new UI engine. Expected Investment Return and Planning Return are distinct prominent measures. Existing projection profiles, including Historical-Calibrated, remain available for compatibility; historical simulators, rankings, saved portfolios and other app features are preserved.
- Component-based forward market assumptions; FRED Treasury rates and optional T10YIE breakeven proxy; missing valuation/institutional components disclosed. Dated institutional ensemble and market valuation inputs supported through advanced JSON. No silent fixed 7% fallback in Forward Planning.
- Per-security decomposition, negative expected returns, zero historical stock-alpha contribution, configurable signal horizon weights, parameter uncertainty and observed log-return risk covariance. No automatic horizon-based return decay.
- Nine structural scenarios, stochastic transitions, stress correlation matrices, volatility clustering, truncated Student-t log shocks, gaps and low-frequency permanent impairment. These are disclosed scenario assumptions, not empirically established probabilities.
- Adaptive Monte Carlo, centered variable-block historical bootstrap and Factor/CMA comparisons; disagreement changes planning uncertainty. The legacy Historical-Calibrated profile still provides uncentered historical scenarios.
- Inflation-adjusted net spending by default; estimated account-type taxes, fees, spreads, sale priorities, RB/NR, average cost basis, optional PAL interest/calls/repayment and liability-adjusted balances.
- Goal success, survival, real principal preservation, fully-funded spending, depletion timing, inverse initial-spending solver with disclosed sample count, three planning cases, sequence tests and ten illustrative stresses.
- Basic/Advanced views, trust diagnostics, audit records, date-bearing cash-flow tables, withdrawal sales per ticker, PDF and Excel export. PDF reuses the existing dark report theme and includes reliability, decomposition, assumptions, percentile chart and annual checkpoints.
- Point-in-time snapshot freezing, vintage filtering, historical selection/forecast runner, nonoverlapping calibration, signed forecast bias and guarded past-only bias correction. A synthetic fixture exercises selection, projections and delisted outcome handling; this is software verification, not empirical validation.

## Validation
681 automated tests passed, including financial invariants A-L and all existing regression tests. Streamlit AppTest rendered the new controls/results with no exceptions (17 metrics, 8 tables in the checked Basic View). PDF text and representative rendered pages were checked; report generation also passed automated tests. A 10-year, 500-path fixture with taxes/PAL and a 150-path solver completed in approximately 9.5 seconds locally before the final risk-covariance refinement. This is not a Render benchmark.

## Open acceptance items and material limits
Full acceptance is NOT established for unbiased empirical calibration. Complete historical universe membership, publication-vintage fundamentals, sector changes and delisted terminal returns are not bundled. Current-data-only runs correctly show LIMITED / UNVALIDATED. See ACCEPTANCE_5_11_35.md.

Institutional CMA/aggregate valuation data need dated inputs; they are not silently scraped or invented. ERP and normalized growth remain explicit configurable assumptions. Scenario, impairment and signal coefficients require out-of-sample validation. Tax modeling is estimated average cost; PAL checks are monthly, not lender-grade collateral operations. Lifetime-style means a user-selected finite horizon up to 50 years, not mortality simulation. Factor exposure completeness remains limited. Stress outcomes are illustrative, not exact historical portfolio replays.

Legacy projection profiles retain their earlier assumptions for reproducibility, including their fixed anchor; Forward Planning does not use those legacy expected-return estimates. Risk preparation still reuses existing data-quality/fallback infrastructure.

## Deploy
Upload extracted contents to repository root; retain durable user data. Upgrade ZIP excludes live snapshots, histories and generated user PDFs. Keep existing FRED_API_KEY in Render Environment. No new required environment variables. Select Future Projection -> Forward Planning. If rates cannot load, enter a dated Treasury assumption through Planning overrides; the engine reports the missing evidence instead of inventing an anchor.

GitHub/Render were not changed. Production browser/mobile behavior has not been verified on Render.
