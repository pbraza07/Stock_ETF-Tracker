# MarketScope 5.11.59 — Favorite Picks missing-evidence fix

Reproduced a TypeError during Favorite Picks when an otherwise eligible stock has a short daily history. The provider correctly returns None for unavailable 20/50/200-day returns; the ranking previously called float(None), aborting the entire run. The screenshot hides the underlying exception, so this reproduction identifies a concrete failure path, not proof of every live failure's cause.

- Safely parse unavailable live measurements as missing, never as zero returns.
- Retain the completed-annual-history requirement; do not assume unknown instruments are stocks.
- Show daily observation count, unavailable evidence, and measured 20/50/200-day returns in results and CSV exports.
- A partial history's maximum is not presented as a verified 52-week high (252-observation convention).
- An incomplete trend uses an explicitly labeled neutral model score; its live-data quality is Low. These are model assumptions, not fabricated observations.
- Show a visible incomplete-evidence warning and per-symbol details. Existing historical model assumptions and imputation disclosures remain intact; this patch does not assert model accuracy or guarantee returns.
- Keep completed rankings available if history persistence fails. Log future failures with their stage and a diagnostic reference instead of losing the underlying traceback.
- Preserve the v5.11.57 session-retention and v5.11.58 market-loading fixes and all existing portfolio features.

Validation: regression tests cover 1/25/100/200-day histories, exact price-derived returns, unknown classification and insufficient annual evidence. The retrieved repository snapshot contains 69 finalists; the 5,000-path calculation is also exercised using explicitly labeled historical fallback, without claiming new live enrichment. No retrieved market snapshot or credentials are distributed in this package.

Deployment: update the existing repository with this package and deploy through Render. Confirm version 5.11.59. This deliverable has not been deployed to the live service. Render logs were not inspected because the connected account requires explicit workspace selection.
