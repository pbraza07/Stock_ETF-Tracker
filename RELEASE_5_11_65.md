# 5.11.65 — Free historical evidence

Adds an on-demand evidence panel to Recession Indicators and completed Forward Planning results. No paid feed or new dependency. Macro requests use the existing free FRED_API_KEY and exact as-of vintage dates; never substitute revised current values for unavailable historical data. SEC companyfacts retain units, fiscal durations, accession and filing date, excluding filings not yet known at the cutoff. Filing-date availability is conservatively the following day. Direct CIK supports firms missing from today's ticker mapping; it does not supply a historical universe.

Results use shared cached retrieval and remain in session state after a failed request. Download JSON includes cutoff, retrieval timestamp, source and content hash. Standard US-GAAP coverage is partial. SEC_USER_AGENT can identify the operator with a contact address if desired; default identifies the public project repository. Requests are bounded and serialized within this collector. Provider blocks are reported, never bypassed.

This is an evidence acquisition feature, not completed empirical calibration. No independent quote feed, delisting payouts, full historical membership or historical analyst estimates are fabricated. Evidence is not automatically transformed into production model ratios: fiscal periods, denominators and units require explicit mapping. Original calculation model version remains 5.11.64 because no numerical assumptions changed. App release is 5.11.65.

Validation: cutoff/restatement isolation, unit/duration separation, incomplete vintage rejection, exact vintage request, conservative trust status and UI smoke tests; existing accuracy regressions retained.
