# MarketScope 5.11.5 - Rebuilt Top 12 release

## Source and scope

Recovered from repository commit `0afd88fbecbcd3f614f79ead4ca44e56924a8568`
(5.11.2). The subsequently observed main commit `a688a91c5a8dd191444a6e131a042dabf38b6413`
has an empty tree. This is a new rebuild, not a recovered copy of the lost
5.11.3/5.11.4 packages. Previous source remains in Git history and the saved
5.11.2 archive. No GitHub push or Render deployment was performed.

## Use

Open **Favorite Picks**, then click either Top 12 button. All eligible stocks
enter both scoring models. ETFs, unknown sectors and securities with fewer than
three completed annual observations are excluded. Sector aliases are normalized
so equivalent sector labels cannot evade the four-stock cap. If 12 qualifying
stocks cannot be selected under the cap, the app explains the insufficient data
or diversity rather than inventing picks.

Scores are percentile-normalized across the eligible universe. All weighted
contributions and penalties appear in the candidate audit and Excel export.
The recession model prioritizes stress defense, drawdown, recovery and Bear P10/P25;
the growth model uses multiple historical horizons and governed P50/P75 forecasts.
Dollar single-stock forecasts assume $100,000; forecast returns are five-year CAGR.
Scores are relative research measures, not probabilities of investment success.

The one-point replacement threshold gives eligible incumbents bounded selection
priority. Final displayed ranks follow actual score. An incumbent can still leave
when it becomes ineligible or cannot satisfy the sector cap.

Build an equal-weight or score-weighted portfolio to compare rebalanced and
non-rebalanced paths using the existing Future Projection engine. Twelve equal
weights sum to exactly 100% internally. Recession portfolios use its existing
Stress Test profile. Existing historical simulation math is unchanged.

## Data and validation limits

- Recent supplemental data is fetched by the existing Yahoo/FRED infrastructure;
  prices and forecasts are not hardcoded. Network availability and freshness
  determine the available evidence; historical fallback is labeled.
- Exact stress windows use complete observed monthly history when it is present.
  Otherwise stress results use explicitly labeled annual approximations. Monthly
  drawdowns, negative-month counts, benchmark-relative stress metrics and six/twelve
  month post-trough returns remain unavailable without the required observations.
- The recovered repository does not contain monthly return files. The existing
  refresh workflow produces them; this release does not pretend they were verified
  in the recovered snapshot.
- Historical studies truncate prices/returns and omit current quote/fundamental
  signals from past scoring. **Current universe membership and sector labels remain
  a survivorship/classification limitation.** The study is explicitly exploratory.
  Point-in-time membership, sector classifications, delisted-security returns and
  archived fundamentals are needed for certified unbiased ranking validation.
- The displayed exploratory hit-rate is not an independently validated predictive
  model quality score. Five-year stock percentile coverage and median errors are
  reported when observations exist. The complete requested recession-specific
  calibration score and certified no-look-ahead acceptance gates remain open.
- No claim of superior out-of-sample accuracy is made.

## Performance

Future Projection and Favorite Picks render their expensive work only while open.
Input state survives tab changes. Projection/ranking exports use bounded caches
keyed by their complete results. Monthly datasets are reused instead of repeated
per-stock history requests. No unchanged Top-50 historical ranking is regenerated
when a Top 12 portfolio input changes.

Local check: 168 eligible stocks, two 5,000-simulation ranking scenarios in about
2 seconds; 12-stock, ten-year, both-strategy projection in under one second.
These timings exclude supplemental network downloads and are not a Render latency
guarantee. First live requests and a full historical study can take longer.

## Files

- `top12_rankings.py`: eligibility, stress evidence, scoring, cap/stability and study.
- `top12_simulation.py`: batched single-stock governed projections and loss metrics.
- `top12_history.py`: independent append-only histories with atomic writes/merge retry.
- `top12_data.py`: durable actual-monthly dataset loader.
- `top12_ui.py`: ranking buttons, evidence, 12-stock portfolios, reports and history.
- `top12_exports.py`: PDF/Excel reports, methodology and limitations.
- `runtime_performance.py`: presentation caches and tab input retention.
- `scripts/update_top12_rankings.py`: scheduled recalculation and durable history.
- `app.py`, `future_projection_ui.py`: lazy navigation and export wiring.
- `future_projection.py`: additive wealth/volatility summary fields only.
- `scripts/update_snapshot.py`: missing NumPy import repair.
- Workflow, version, documentation and regression tests.

## Deployment

1. Back up the current repository and durable `data/` files.
2. Extract the ZIP **into the repository root** so `app.py`, `requirements.txt`,
   `render.yaml` and `VERSION.txt` are at the root. Do not upload only the ZIP or
   nest its contents under another directory. This addresses the earlier Render
   `requirements.txt` not found error.
3. Overlay code without deleting existing saved portfolios, generated PDFs,
   snapshots, Favorite Picks history or either Top 12 history ledger. The release
   intentionally excludes live user libraries and ships upgrade-safe bootstraps.
   If recovering the empty main tree, restore durable files from the preserved
   prior commit/backup before refreshing.
4. Keep Render's existing Python 3.12.11, requirements build command and Streamlit
   start command from `render.yaml`. No new dependency or secret names are needed.
5. Retain `MARKETSCOPE_GITHUB_REPO`, `MARKETSCOPE_GITHUB_BRANCH`, and
   `MARKETSCOPE_GITHUB_TOKEN` (Contents read/write) for durable manual history saves.
   Without the token, the app warns that its history is server-local. The scheduled
   workflow uses the existing `GITHUB_TOKEN` with Contents write permission.
6. Deploy, run the existing refresh workflow, inspect its logs, then check both
   buttons and generated reports. No deployment or live-provider success is
   implied by local tests.

## Acceptance status

Automated calculation/regression checks and Streamlit control tests are run on
the release contents. Desktop/mobile browser visual QA could not be completed
because the provided browser blocked the local preview address. Responsive tables
use native horizontal scrolling with pinned Rank/Ticker; final deployed-device
verification is still required. See `VALIDATION_5_11_5.md` for measured results.
