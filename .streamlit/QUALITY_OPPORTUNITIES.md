# Quality Growth & Return Opportunities — 5.11.38

## Status and scope

New research tab, not an investment recommendation or a proven 25% strategy. Uses the existing MarketScope stock universe, quality evidence and Forward Planning path generator. Existing Favorite Picks, historical simulators, Future Projection profiles and exports remain available. Version 5.11.37 connection settings are retained.

### Target definitions

- Next 12 months: net terminal total return >= target; horizon forced to one year.
- Annualized over horizon: net terminal CAGR >= target (1, 3, 5 or 10 years in UI).
- At least target every year: every modeled anniversary-year return >= target. Not equivalent to CAGR.

Costs are explicit, not silently assumed zero: default annual cost 0.10%, one-way transaction cost 0.10%; both configurable. Entry and final exit incur cost. Yearly rebalancing incurs cost on actual absolute turnover. No leverage, withdrawals or taxes in this opportunity screen. The existing financial-planning workflow retains those features.

## Current architecture

- `quality_opportunities.py`: universe checks, quality evidence, forward single-stock paths, target/downside gates and joint RB/NR portfolio evaluation.
- `quality_opportunities_ui.py`: lazy dashboard tab, form controls, background jobs, audit and results downloads, paper-record save.
- `opportunity_walk_forward.py`: cutoff-frozen offline stock-screen evaluation against supplied realized outcomes and benchmarks.
- `opportunity_paper.py`: explicitly requested immutable research snapshots, local plus configured GitHub persistence when available.
- Existing `planning_assumptions.py`, `planning_paths.py`, `future_projection.py`: reused without financial formula edits for this feature.
- Existing `projection_jobs.py`: shared one-active-job scheduler prevents overlapping large jobs across Future Projection and this screen.

## Eligibility and quality

No embedded ticker selections. All current Type=Stock records are inspected; each security requires a valid sector, positive snapshot price and forward P/E, >=75% fundamental coverage, credible completed annual risk history and >=24 observed monthly returns. Each exclusion has a reason. Missing valuation or history is not fabricated. This can exclude promising loss-making businesses; it is an intentional quality-screen constraint, not a judgment that they cannot appreciate.

Quality components: ROIC (ROE fallback), operating margin, free-cash-flow yield, revenue growth, earnings growth and debt/equity. Within a sector with >=5 observed values for a metric, use percentile ranks (inverse for leverage). Missing metrics contribute zero; the score denominator is not reduced. With smaller peer sets, use explicit linear absolute scales: ROIC/ROE 0–25%; margin 0–25%; FCF yield 0–8%; revenue growth 0–20%; earnings growth 0–25%; debt/equity 0–200 (lower better). These are heuristic research scales, not statistically optimized parameters.

Financial-sector companies omit FCF yield and debt/equity. ROE and margins remain imperfect comparisons for banks/insurers; regulatory capital, credit quality and sector-specific valuation are not fully modeled. Current fundamentals are not evidence of durable multi-year business quality by themselves. Competitive advantages, earnings quality, margins over a cycle, analyst dispersion, credit ratings and long-run reinvestment performance require further data. This release does not claim those missing dimensions are implemented.

Quality is separate from price attractiveness: forward P/E enters the existing expected-return decomposition. Historical stock CAGR is not used to set forward return. Expected Investment Return is first-year geometric drift before modeled gaps/impairments/costs. Planning Return is P25 net simulated CAGR; neither is a safe withdrawal rate. Forward Planning's existing return bounds and model assumptions are not loosened to generate 25% recommendations.

## Selection and portfolio results

Calculate model outcomes for every data-eligible stock, then apply quality, target probability, terminal loss probability, terminal >20% loss probability and worst-decile mean return constraints. Sort qualifying stocks by target probability, then quality, then ticker. Show up to five per sector; do not fill missing slots. The all-stock table preserves failed constraints.

Portfolio selections are user-controlled from all qualifying stocks, not just the five displayed sector leaders. Up to 12 equal-weight holdings; configurable position and sector caps. Joint simulation requires >=24 common observed monthly returns. Correlations vary with the existing structural regime model. RB resets annually; NR drifts. No average of individual probabilities is used. Interim risk is measured monthly, not as daily drawdown. Effective independent holdings is a correlation approximation, not a count of distinct businesses or a full factor-risk measure.

If no stocks meet the constraints, show an empty qualified result explicitly. If neither evaluated portfolio meets them, say so. This is not an exhaustive proof that no imaginable portfolio qualifies: automatic global portfolio optimization is not implemented. A proposed or realized 25% gain does not establish repeatable annual gains.

## Confidence and auditability

Always label probabilities UNCALIBRATED MODEL ESTIMATE (UI uses uppercase). MC interval bounds describe finite-sample simulation noise only, not true forecast uncertainty. Audit contains component model mean CAGRs, disagreement, decomposition, input settings, timestamps, source failures, scored universe and exclusions. Report LOW strategy confidence until proper external validation. No empirical backtest score or high-probability certification is fabricated.

Live data is reused through existing MarketScope monthly/live loaders. Loading the whole stock universe can take time or encounter provider limits. Jobs run on explicit request, not every page interaction. Results retain completed-run settings and snapshot context for consistent portfolio evaluation. Refresh data and rerun to update them. Retrieval timestamps are not financial statement publication timestamps; missing/stale source information must remain visible. Existing data-source failure messages are retained.

## Point-in-time test bundle

Run `python opportunity_walk_forward.py bundle.json output.json` from the repository root.

Bundle keys:

- `records`: rows with `kind`, `key` (symbol or macro series key), `value`, `observation_date`, `available_at`. Dates must use a consistent timezone convention.
- `kind=universe`: value object with eligible, name, type, sector, price, market_cap, as actually known then. Include inactive/delisted membership records, not only today's survivors.
- `kind=fundamentals`: normalized MarketScope fundamental object as published at that time, not today's revised values.
- `kind=macro`: numeric value; e.g. key `treasury_10y`, percent units.
- `kind=prices`: completed annual total return in fractional units, observation date December 31.
- `kind=monthly`: actual total return in fractional units, observation date month end.
- `cutoffs`: December 31 historical dates. The runner rejects non-year-end cutoffs because its realized outcomes are annual.
- `screen_settings`: the same fixed screen controls, chosen before evaluation. Do not tune them on final test outcomes.
- `realized_annual_returns`: symbol -> year -> return fraction. Include delisting loss and subsequent cash-slot returns. Outcomes never enter screening.
- `sp500_annual_returns`: year -> total return fraction.
- `sector_annual_returns`: point-in-time sector label -> year -> benchmark return fraction.
- `delisted_coverage_documented`: optional provenance assertion, not an automatic certification.

Both available_at and observation_date must be <= cutoff. Latest revisions available at that cutoff are used; current live loaders are never called. Outputs include all selected stock forecasts, outcomes, probability bins, realized-minus-P50 bias, benchmark hit flags, missing outcomes and nonoverlapping calendar-window count. Dates alone do not verify vendor provenance. Same-date securities and overlapping windows are correlated; probability-bin counts are NOT independent trial counts. Benchmark gaps remain missing. Current implementation validates sector leaders, not discretionary portfolio construction, and cannot infer daily drawdown from annual outcomes.

A genuine training/calibration/untouched-test split, vendor provenance review, robust confidence intervals clustered by period, complete historical membership, portfolio-policy backtests and ongoing realized paper-record evaluation are still required before any predictive claim. No such empirical data is bundled. This release provides the research and test machinery, not evidence of a profitable strategy.

## Paper record persistence

The Save button writes a new UUID-named JSON file under `data/quality_paper_records`, never overwriting past records. When the existing configured GitHub token permits repository writes, the file is mirrored there. The UI warns that repository readers can see selected tickers and estimates. No trade is placed. Local-only records can disappear on hosted redeploy, so use the audit download backup. Records do not automatically become completed outcome evaluations: reconcile dated total-return observations before assessing success.

Release packaging excludes paper records and other existing durable user datasets. No deployment or repository mutation is performed by creating this release package.
