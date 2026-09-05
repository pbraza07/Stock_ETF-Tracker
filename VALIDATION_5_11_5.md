# Validation - MarketScope 5.11.5

Checked September 5, 2026 using the recovered September 4 market snapshot.

## Automated and local checks

- Full release regression suite: 549 tests. See packaged pytest output for the
  final pass/fail result. Historical simulation routines were not altered.
- New tests cover full eligible-universe evaluation, sector caps and aliases,
  reproducible percentiles, stability thresholds, immutable ledger history,
  exact monthly stress windows, 12-stock Both projections, input retention after
  lazy navigation, and export cache invalidation.
- Streamlit control harness: ranking buttons, portfolio build and historical
  study controls complete without exception elements or error banners. The
  harness replaces external providers and persistence with local fixtures.
- Real recovered snapshot: 397 total instruments, 175 stocks, 168 eligible stocks
  evaluated. Each ranking selects 12 stocks with no sector above four.
- Local 5,000-path ranking calculation: approximately 2.0 seconds, excluding
  live-data acquisition. Twelve-stock, ten-year Both projection: approximately
  0.8 seconds. These are single local checks, not production service guarantees.
- PDF and Excel exports generated successfully, including both portfolio
  strategies. A PDF stock-detail page was rendered and visually inspected for
  legible text, ordered percentiles and unclipped table content.
- Repository-root ZIP check ensures `requirements.txt`, `app.py`, `VERSION.txt`
  and `render.yaml` exist at the archive root. User-owned live ledgers, saved
  portfolios and generated PDFs are excluded to avoid overwrite on upgrade.

## Exploratory historical study

42 usable ranking/horizon observations across historical training cutoffs were
produced in approximately 8 seconds locally. Twelve observations support five-year
stock-percentile comparisons. Mean coverage across those observations:

| Ranking | P10-P90 coverage | P25-P75 coverage | P50 median absolute CAGR error |
|---|---:|---:|---:|
| Max Profit | 88.89% | 73.61% | 9.93 percentage points |
| Recession | 86.11% | 56.94% | 6.24 percentage points |

These are exploratory single-stock outcome diagnostics, not portfolio interval
coverage, not stress-conditional Bear calibration, and not an accuracy guarantee.
They are subject to current-universe survivorship and current-sector bias.
The CSV evidence is under `validation/top12_exploratory_validation.csv`.

## Unverified or blocked acceptance gates

- Certified no-look-ahead ranking validation needs point-in-time sector and
  universe membership, delisted-security outcomes and archived fundamental
  inputs. Those datasets were not present. No certified model backtest score
  or superiority claim is asserted.
- The complete requested recession-specific validation score remains open;
  annual-resolution fallback cannot certify intramonth stress behavior.
- The recovered commit has no actual monthly-return files. Synthetic monthly
  regression cases passed, but fresh provider data was not acquired or verified
  for the entire recovered universe in this run.
- Desktop/mobile browser visual QA is unverified: the available browser blocked
  the local preview URL. Native responsive Streamlit tables and pinned columns
  are implemented; check the deployed view on target devices before acceptance.
- GitHub Actions and Render were not executed or deployed by this build. Live
  provider availability, scheduled persistence and deployed console state require
  post-deployment verification. No current data was labeled intraday-live based
  solely on local testing.

Existing analytics emit NumPy timedelta deprecation warnings under the test
runtime. They did not fail tests; this release intentionally does not change
historical-return calculations to silence them.
