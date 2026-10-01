# MarketScope v5.11.39 — All stock results and criteria ranking

The Quality Growth & Return Opportunities main results table now displays every stock in the current universe, including stocks that fail screening and stocks that cannot be scored. ETFs remain outside this stock screen.

Rows are ranked by number of the five configured screening criteria met, descending: quality score, target-return probability, loss probability, severe-loss probability, and worst-decile mean return. Ties preserve the existing target-probability, quality-score, ticker ordering. Missing-evidence rows appear last with no invented estimates. Rank, criteria met and criteria assessed are visible.

Failed numeric cells are highlighted red. Amber notes state actual and required values. Passing rows have green status text; unscored rows have gray status and an explanation. CSV, audit JSON and optional paper records include all results. The qualified sector shortlist remains available separately.

Expected-return estimates, risk calculations, qualifying rules, and joint-portfolio eligibility are unchanged. Calculation model version remains 5.11.38-quality-1; application release is 5.11.39. A high screening count is not a calibrated probability or a guarantee of returns.

This is a cumulative source package, not a deployment. Existing user data are excluded by the release packaging policy.

Validation: 708 automated tests passed (72 warnings). Targeted tests cover criteria-count sorting, tie ordering, all-stock visibility, missing evidence, threshold boundaries, notes and highlighting.
