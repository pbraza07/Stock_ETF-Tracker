# MarketScope v5.11.62 — Median target and quote-date data flow

The circled median and implied-upside fields were empty because the daily snapshot omitted Price Target Median even though Yahoo supplied it. Target fallback retrieval also stopped after finding low/mean/high. Price As Of treated the placeholder em dash as a real quote date, preventing fallback to the available snapshot timestamp.

Changes:
- Retrieve true median targets through the provider fallback chain, independently of the average.
- Persist and hydrate the median through daily snapshots, session target reuse and normalized market rows. Carry a separate median retrieval date when preserved across partial refreshes.
- Retain actual daily quote observation dates in generated snapshots.
- Ignore null/placeholder date values. Where only the refresh time is known, display "Snapshot refresh: ...", not an invented quote timestamp.
- Include verified, dated analyst targets for 162 of 163 tracked stocks so both saved ranking tables can populate immediately without depending on a new provider call from Render. No analyst data was returned for CCZ; no replacement estimate is invented.
- Use a new background-cache namespace and serial target requests to avoid retaining the earlier median-less cache and reduce provider contention.
- Compare target-source dates. Prefer the newest reported median-containing target group. If a newer response omits the median, keep the earlier group intact with its original dates and an explicit status; do not splice fresh low/high into older median data.
- Continue calculating Median Target Upside % from the actual median and displayed quote. Missing medians remain missing with a diagnostic status. Mean and median are never interchanged.

Validation covers provider fallback, immediate use of persisted verified targets, placeholder/NaN dates, newer snapshot precedence, incomplete-source consistency, exact upside arithmetic and original ranking/export regression tests. Ranking scores, financial formulas, portfolios and unrelated features are preserved.

Deploy through the existing GitHub main → Render workflow. No new paid infrastructure or credentials are required.
