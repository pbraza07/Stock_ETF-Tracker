# MarketScope 5.11.64 — investment evidence and probability integrity

## Calculation corrections
- Yahoo revisions use one forecast period (+1y preferred) and 30-day upward/downward counts: (up-down)/(up+down). Zero coverage remains missing. Price-target distance never substitutes for a revision.
- Forward growth reads only the company's +1y estimate. Industry, sector, index, quarterly and multi-year values are not pooled.
- Genuine zero ROE receives the appropriate quality adjustment; missing remains distinct.
- Top-five sector forecasts reuse Forward Planning CMA, signal horizons, monthly regime paths, centered bootstrap and impairment modeling. Historical scoring weights remain unchanged; selected-stock historical means no longer drive these forecasts.
- Missing CMA leaves candidates visible and probability fields missing, with no forecast-score credit. Archived rankings retain their original version and numerical values.
- Rankings measure simulated drawdown monthly. Monthly measurements still cannot capture intraday extremes.
- Screening ties prioritize evidence coverage and quality after criteria count.

## Retirement and data integrity
- XNYS exchange calendar detects missing trading sessions in YTD histories. Runs with gaps fail clearly and leave the previous result intact. Holidays/weekends are not missing observations. No synthetic prices are generated.
- Impaired slots retain recovery as zero-return cash; RB/contributions cannot buy them again. If all holdings fail, contributions remain cash.
- Contributions have their own selectable cadence.
- Sustainable withdrawal search uses common random numbers, a one-sided Wilson sampling lower bound and disjoint holdout paths. Failed holdout checks do not produce a supported withdrawal amount. This controls sampling uncertainty, not model uncertainty.
- Forward reports contain the versioned raw calculation input snapshot and SHA256 digest. Provider observation time, retrieval time and unavailable vintage are separate.
- Old cached analyst-growth fields are invalidated; observed saved results are not deleted.

## Validation and education
- Historical simplified legacy checks are labeled UNVALIDATED; their diagnostics are not marketed as exact-model validation or leakage-free proof.
- Point-in-time runner uses the production ranking function on cutoff-frozen evidence, then the production Forward Planning engine. Realized comparison is annual equal-weight rebalancing before costs, and reports this limitation.
- Calibration separates nonoverlapping test periods by horizon; reports Brier scoring and reliability bins when realized probability records are supplied. Old/wrong-model records cannot certify this model or drive bias correction.
- Observed selected-stock stress replays are distinct from illustrative style shocks. Missing full windows are listed, never backfilled.
- UI/PDF explanations distinguish conditional probabilities, empirical validation, shared model assumptions, analyst targets, and news impact interpretation.

## Data-dependent limits (not claims of completed empirical validation)
No licensed point-in-time universe, full delisted returns, publication-vintage fundamentals, independent quote feed or dated institutional CMA ensemble was supplied with this release. The software includes the frozen-data runner, same-basis independent-quote comparison contract and missing-coverage disclosures, but cannot manufacture these observations. Forecasts remain unvalidated conditional estimates until an adequate out-of-sample dataset is provided and evaluated. The shipped cross-source contract does not claim a live second source is connected. Historical calibration retains survivorship limitations. More Monte Carlo paths do not eliminate these limitations.

## Migration
No database schema change. No saved rankings, portfolio simulations, news, PDF files or source data are overwritten. New calculation/cache contracts use 5.11.64; older completed results remain available with their original timestamp/version. Legacy projection profiles remain available and are explicitly exploratory. Production deploy is a single source commit based on the current GitHub main tree, retaining concurrent data refresh files.
