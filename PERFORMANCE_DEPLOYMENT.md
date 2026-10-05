# MarketScope 5.11.56 — performance release

## Deployment modes

The existing `render.yaml` remains compatible with the current single-service deployment.
Calculations now run in a child process; SQLite WAL stores queued jobs and completed results.
For durable single-host storage, set `MARKETSCOPE_STATE_DIR` to a private persistent disk directory.
Without a persistent disk or PostgreSQL, local runtime data is lost on service replacement.

For external audiences, use **render.public.yaml** as the Blueprint path. It provisions an
always-on web service, independent calculation worker, scheduled collector, and PostgreSQL.
These are paid hosting resources; this release does not provision or change your live services.
Web, worker, and collector must run the same release and share `MARKETSCOPE_DATABASE_URL`.
Set FRED_API_KEY and GitHub credentials on the shared environment group. Also copy optional
OPENAI_API_KEY and MARKETSCOPE_NEWS_SUMMARY_MODEL there when summaries are enabled.
Never place credentials in the source archive. `MARKETSCOPE_EXTERNAL_WORKER=1` on the web
service prevents spawning an additional local worker. Start one calculation worker first;
scale workers only after measuring peak RAM per task. No simulation-count reduction is applied.

The cron collector refreshes the shared public datasets every 15 minutes. Cached data is
shown immediately; observations keep their source dates. An unsuccessful refresh retains
previous data. News manual refresh uses a shared lease to prevent duplicate collectors.

## Queue behavior

Reports receive priority over interactive calculations, followed by full-universe screens.
Waiting time increases priority to avoid starvation; each priority class starts oldest jobs first.
Maximum 20 outstanding jobs by default (`MARKETSCOPE_MAX_QUEUED_JOBS`), at most two
per browser owner. The private recovery ID is a bearer credential: keep it private. Enter
it in Future Projection's recovery section after losing the browser session. Jobs and reports
are retained 24 hours. Queued jobs survive restart. A running job whose worker heartbeat is
lost is marked failed after two minutes; it is not automatically repeated. Cancellation is
cooperative at progress checkpoints; a provider call already in progress finishes first.
Browser-owner limits are not account authentication. Add authenticated per-account quotas at
the gateway before offering unrestricted public compute. Existing shared saved-portfolio/GitHub
features retain their existing visibility; do not store private client portfolios there without
an ownership/access-control migration. PostgreSQL credentials are server-only. Serialized jobs
are trusted server-created Python objects and must never accept arbitrary client payloads.

## What changed

- All top-level workspaces conditionally render; nested Portfolio pages also render on demand.
- Portfolio Build outputs persist across navigation into Saved/Manage.
- News and Recession pages skip the market snapshot startup pipeline.
- GitHub startup reads serve cached/local data first and refresh off the rendering path.
- Projection and quality input retrieval occurs in the calculation worker.
- Per-security provider caches reuse overlaps between stock baskets; source failures back off.
- Future Projection reports are prepared by format on demand in the worker and retained.
- Saved portfolio cards paginate by ten and prepare a requested PDF only; saved as-of values
  are preserved instead of silently enriching each report with newer quotes.
- News articles and security references are indexed in shared storage; original JSON archives
  remain supported for import/export and GitHub mirroring.
- Interactive recession charts use a reusable local component with a shared Plotly asset;
  static fallback, recession bands, and All History remain available.
- Streamlit presentation caches have explicit entry limits.

## Validation and operations

Run `python -m pytest -q`. Performance-specific tests cover queue FIFO/backpressure, recovery,
expired worker heartbeats, stale-while-refresh behavior, and overlapping-symbol reuse.
Use `python tools/performance_probe.py --jobs 10` against an isolated deployment database to
measure queue completion; never run synthetic stress tests against user jobs. Measure p50/p95
startup, tab latency, peak RAM, worker queue wait, provider errors and reconnects at 1, 10, 25,
and 50 concurrent sessions. Suggested targets are warm useful content under 2 seconds, cached
tab changes under 1 second, and submission acknowledgement under 1 second. They are acceptance
targets, not measured production guarantees. Network/provider failures and cold caches must be
included in the deployment test. Existing calculations must retain fixed-seed regression results.

Back up PostgreSQL before migration. Retain the prior release ZIP for rollback. Existing JSON
and CSV files are not deleted. The new private runtime store can be removed only after backing
up desired job results/news; rolling back does not require deleting it.

## Verification boundaries

Automated regression and UI navigation checks run against local SQLite, with network-dependent
navigation inputs replaced by deterministic fixtures. A separate worker process has been checked
against a direct fixed-seed projection for matching RB/NR financial tables. PostgreSQL configuration
and SQL paths are included, but a live PostgreSQL/Render integration test and real multi-user load
test are still required before public launch. Browser automation for the custom chart could not be
run in the build environment; native component registration and static fallback are regression-tested.
No paid Render resource was provisioned, and the live app was not redeployed by this release.
