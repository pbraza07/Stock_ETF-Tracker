# MarketScope 5.11.56 — performance upgrade

Built from v5.11.55. No financial return model, RB/NR mathematics, historical
calibration, withdrawal rules, or existing feature family was removed.

## Included changes

1. Active-tab execution for all ten workspaces and the three Portfolio subtabs.
   Input-state preservation excludes button triggers. Build results carry into Saved/Manage.
2. News/Recession startup skips unrelated market dataset assembly. Snapshot loaders
   show saved data first and refresh in the background, retaining source timestamps.
3. Durable queued projection/quality/report jobs. Calculation and data acquisition run
   outside the UI process. Bounded queue, browser-owner quotas, private recovery IDs,
   cooperative cancellation, explicit interrupted-job failures, and 24-hour result retention.
4. Report priority over interactive calculations and full-universe screens, with aging.
5. Shared per-security caches, overlapping-basket reuse, provider budgets, cooldowns,
   duplicate-request coordination, bounded presentation caches, and PostgreSQL pooling.
6. On-demand PDF/Excel/CSV by requested format. Saved portfolio cards paginate by ten;
   Open/Share restores an absent PDF only when requested. Saved report dates are preserved.
7. Indexed news storage, stock/date/publisher/text filtering, SQL pagination, and versioned
   impact indexing. Feed collection and GitHub mirroring are off the rendering path.
8. Reusable versioned local Plotly component asset for all recession charts, retaining
   static fallback, All History, titles, explanations, and recession shading.
9. Conservative worker-memory admission checking in addition to existing memmap handling;
   requested simulation counts are never silently reduced.
10. Optional public Render Blueprint with separate web/worker/collector/PostgreSQL services,
    plus migration, rollback, configuration, and measurement guidance.

## Verification

- **820 automated tests passed** in the local Python 3.12 environment.
- Main-page navigation and Portfolio Build → Saved/Manage → YTD → Build navigation passed
  with deterministic provider fixtures; no hidden-page dependency errors remained.
- A separate worker process produced the same fixed-seed RB/NR financial tables and
  comparison as a direct projection run.
- A ten-job local queue probe completed successfully. This is a functionality probe,
  not a production concurrency benchmark or response-time guarantee.
- No baseline data/static artifact was changed. No live saved-simulation library,
  credentials, generated fundamentals cache, runtime database, or job results are shipped.

## Deployment-dependent verification

The live MarketScope service has not been redeployed. The PostgreSQL/Render topology
requires provisioning and live integration testing. Multi-user load testing at 1, 10,
25, and 50 sessions remains necessary to size worker capacity. Browser automation for
the new chart asset could not run in the build environment; component registration
and static fallback are tested. Existing shared saved-portfolio access must be reviewed
before hosting private portfolios for unrelated users.

See PERFORMANCE_DEPLOYMENT.md for the concrete rollout instructions. The existing
single-service configuration remains available; the public topology is opt-in.
