# v5.11.26 - Macro refresh recovery

Diagnosed run: https://github.com/pbraza07/Stock_ETF-Tracker/actions/runs/34930241131
All three FRED series reported ReadTimeout. FRED_API_KEY was empty in the
Actions job. These are data-download failures, not recession signals.

Fixes: scheduled downloads use 30-second read timeouts and two attempts for
transient failures; three series download concurrently. When configured API
access fails, use official FRED CSV. Preserve validated old snapshots without
changing their freshness. Show per-series job summaries, secret configuration
status (never the value), and isolate collection failures. Pin macro dependencies
to application-compatible major versions. Retain failure status when no fresh
data can be saved instead of hiding provider outages.

Required setup:
1. GitHub repository Settings > Secrets and variables > Actions > New repository secret.
2. Name: FRED_API_KEY. Value: your valid FRED API key (no surrounding quotes).
3. Upload the extracted release files, including .github/workflows, preserving data.
4. Actions > Refresh macro snapshots > Run workflow.
5. Confirm each series is Updated and its JSON file was committed.

Render's FRED_API_KEY is separate from the GitHub Actions secret. Keep it on Render
for app-side API access. The patch does not create either secret or bypass provider
restrictions. Live CSV probes also timed out from the development environment;
successful production refresh requires verification after deployment/configuration.
All v5.11.25 YTD statistics and existing simulations are retained.
