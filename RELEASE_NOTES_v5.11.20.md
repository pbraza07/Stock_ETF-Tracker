# MarketScope v5.11.20

Future Projection PDF exports now use the populated dashboard presentation:
- Dark current-market environment cards, risk details and data freshness.
- Side-by-side strategy summary grids using the same fields and formatting as the screen, including holdings, allocations, forecast dates and confidence explanation.
- The current selected graph, visible strategy/percentile lines, range bands, withdrawal and no-withdrawal references. Vector chart export requires no browser or image-rendering service.
- All detailed table columns and periods, paginated into readable groups with repeated dates, green positive values and red negative values.
- Inputs, assumptions and limitations remain included. Simulation calculations are unchanged.

The requested deletion targets only record SIM-20260909-150352-604 (Simulation 9/9/2026). Opening Saved Simulations after deployment removes that ID from local live/bootstrap data and its server/persistent-disk PDF. A retirement filter prevents the record from reappearing from an older remote copy. Background cleanup uses the app's MARKETSCOPE_GITHUB_TOKEN, if configured, to remove the exact remote record and PDF while preserving other saved records. Cleanup uses the current GitHub SHA to avoid overwriting concurrent saves. Failures are logged and retried on app restart.

GitHub rejected direct deletion from this development session with HTTP 403 (integration lacks write access). Remote deletion has NOT been confirmed. App deployment and subsequent cleanup are still required. No unrelated portfolio or data file is deleted by this update.

Install: upload the extracted release contents at repository root while preserving existing data; redeploy and confirm version 5.11.20. Existing saved PDFs remain historical artifacts; run/export a Future Projection to create the new format.

Validation: all 594 regression tests passed, including four new dashboard-export and targeted cleanup tests. Rendered PDF cards, charts and tables were visually checked. Live Render deployment remains unverified.
