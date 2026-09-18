# MarketScope 5.11.32 — Historical-Calibrated projection (experimental)

Select Future Projection → Projection Strategy → Historical-Calibrated. Existing profiles and historical simulator calculations are preserved.

The new mode uses shared observed periods only (no proxy-filled returns), with a minimum of five contiguous years across all selected holdings. It jointly resamples two-year blocks for annual modeling or six-month blocks for monthly modeling. Short/gapped histories produce an explicit validation message; choose the existing model instead.

Recency candidates blend full-history and recent-five-year evidence with recent weights of 0%, 25%, or 50%. Expanding-window one-year log-growth errors select the weight; no later outcomes enter an earlier origin's selection. Additional 1/3/5-year forward error records are provided when available. These tests tune historical recency, not the complete withdrawal strategy or percentile coverage. This does not establish forecasting superiority. Current holdings introduce selection bias and block resampling cannot generate unprecedented single-period shocks. Live regime adjustments are not applied in this mode.

There is no forecast-year decay multiplier. All-path no-withdrawal investment-return percentile columns are added separately; account-return statistics and depletion calculations remain unchanged. For Non-Rebalanced holdings, a no-withdrawal reference may have different weights than an account with cash flows. Dollar profit and balance percentiles still include all account outcomes.

Existing profile calibration scores are not reused as validation for this mode. Confidence is Low and score is unassigned; legacy views formatting missing values as zero must be read as unscored, not measured zero. Audit contains the historical calibration details. Sampling uses a separate fixed seed and preserves prefixes as the horizon increases.

Validation: 660 regression tests passed before the final metadata clarification; final run recorded in validation/pytest_v51132_final.txt. CSV and Excel generation smoke-tested. Production UI and PDF visual verification remain pending. No claim of greater predictive accuracy is made.

Upload the extracted repository-root files while preserving live data, then redeploy. This package has not been pushed to GitHub or deployed to Render.
