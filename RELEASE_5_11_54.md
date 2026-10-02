# MarketScope 5.11.54 — Evaluate every stock

## Cause and correction

The previous quality screen stopped before simulation when fundamental coverage
was below 75%, or when valuation/profitability checks failed. It returned those
stocks only as excluded records, causing NOT SCORED rows even when some quality
or historical risk data was available. Provider failures could therefore leave
the entire screen without estimates.

The revised screen computes evidence-adjusted quality for every eligible stock
and attempts risk/return simulation independently of quality qualification.
Low-coverage and unprofitable companies remain visible and receive supported
calculations. Data sufficiency and profitability gates still prevent unsupported
shortlist qualification. Missing estimates never count as passing a criterion.

- Every stock has an evaluation row, including when CMA or monthly history is missing.
- Quality component coverage and missing field names are exposed.
- Status shows EVALUATED — LIMITED DATA when estimates have missing inputs.
- Where risk history and forward CMA are sufficient, probabilities can be calculated
  using available fundamentals and explicit forward model assumptions. These are
  uncalibrated conditional estimates, not complete company research.
- With no usable fundamentals, the evidence-adjusted quality score is zero. This
  indicates lack of evidence, not proof of a poor business; quality is not counted
  as an assessed criterion in this case.
- Without adequate history or CMA, return/risk estimates remain unavailable with
  reasons; the quality evaluation still completes. No zero probability is substituted.
- Live loader failures are recorded and do not suppress the available evaluation.
- Recent observed fundamental fields are retained locally for up to seven days,
  preserving original retrieval dates in the audit. Missing live fields can use
  these cached observations. Cache recovery does not create missing values and
  requires an earlier successful fetch. Point-in-time backtests never use this cache.
- Older session results display available quality evidence and request a new run
  for updated forecasts. All stocks remain ordered by criteria met.

## Upgrade and verification

Upload this cumulative package through the existing deployment process. Preserve
live portfolio and news data. No new dependencies or keys are required. The local
fundamentals cache is excluded from the package and may be lost on ephemeral
hosting redeploys.

After deployment, open Quality Growth & Return Opportunities and select
**Evaluate current stock universe**. Review Evidence coverage, Notes and the
audit when a row has limited data. A provider outage cannot be made into verified
financial evidence by changing the status label.

Automated checks exercise complete inputs, missing fundamentals for the entire
universe, negative profitability, absent CMA/history, old results, cache expiry,
and the Streamlit screen. Results are in validation/. Production data retrieval
and deployment have not been verified by the assistant.
