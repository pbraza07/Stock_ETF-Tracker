# MarketScope v5.11.34 — Historical-Calibrated return variation

Historical-Calibrated previously replayed exact returns from a small set of observed annual or monthly blocks. This could produce repeated annual percentile values. The mode now samples smoothed joint historical log returns, not literal historical replays.

## Method and scope

- Retains the existing historical block selection and past-only recency-weight calibration.
- Adds joint covariance-based innovations and compensates their variance by shrinking sampled log-return deviations. The mixture preserves the sampled distribution's log mean and cross-stock covariance at each block position in expectation, not exactly in every finite run.
- Bandwidth is explicitly `min(0.25, shared_periods ** -0.2)`. This is a heuristic, not a forecasting-accuracy optimization.
- Synthetic samples can extend beyond previously observed returns. Arithmetic-return means, tail shape, and serial dependence are not preserved exactly; serial dependence is attenuated.
- Fixed seeds reproduce results. Constant histories do not receive invented variability. Input returns at or below -100% are rejected with an explicit message.
- No forecast-year return decay or forced uniqueness is added. Rounded percentile returns can still coincide. Percentiles across years are distribution summaries, not a single continuous investment path.
- Existing withdrawal-account returns and no-withdrawal reference returns remain distinct; depletion-related zeros are valid and retained.
- Other projection profiles and historical simulator calculations are unchanged.

## Trust and validation

This mode remains experimental. Historical recency calibration does not validate the added smoothing, future percentile coverage, or predictive superiority over AUTO. Current-holdings selection bias remains. More variation must not be interpreted as more accuracy.

Regression: 666 tests passed, including seed reproducibility, non-degenerate synthetic variation, conditional log-moment checks, and no invented variation for a constant history. Tests verify implementation behavior, not investment forecasting performance.

## Deployment

Upload extracted files at the repository root and redeploy. Preserve existing saved simulations, ranking histories, and market data; those live files are excluded from this upgrade ZIP. No new environment variables are required. This package has not been deployed or browser-verified on your Render instance.
