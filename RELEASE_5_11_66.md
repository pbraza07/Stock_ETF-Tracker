# 5.11.66 — Free cross-provider checks and prospective forecast records

Adds optional Alpha Vantage end-of-day close comparisons against the matching Yahoo regular-session date. Only USD U.S. exchange identities are accepted; invalid or absent data never gets a MATCH. A 1% tolerance is a discrepancy screen, not exchange-origin certification. Historical active/delisted listing downloads preserve the cutoff and do not assert complete payouts or total returns.

Requires ALPHA_VANTAGE_API_KEY in Render Environment. No credentials are embedded. Cached successful responses last 24 hours, stale responses are labeled, and failures preserve prior displayed work. Shared database request reservation enforces 20 requests per rolling 24 hours and 13-second spacing; other applications sharing the provider key also consume its quota. Provider terms must permit the deployment's use; no paid endpoint is requested.

Completed Forward Planning results can be explicitly frozen and archived using the existing immutable paper-record persistence with a downloadable backup. Records include model version, input evidence, parameters and terminal no-withdrawal reference percentiles. They remain PENDING; an outcome evaluator must reproduce configured contributions, fees, dates and strategy before scoring them. This release does not claim complete historical probability calibration or add an automatic outcome evaluator. Numeric model remains 5.11.64.

Tests cover request budgets, quote identity/nonfinite values, delisting cutoffs, pending forecast provenance, missing-key no-network behavior, retained evidence after provider failures, and prior accuracy regressions.
