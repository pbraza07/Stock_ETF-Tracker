# MarketScope 5.11.38 — Quality Growth & Return Opportunities

## Included

New main dashboard tab: Quality Growth & Return Opportunities.

- Dynamic stock-only screen of the existing universe, no embedded selections.
- Configurable 25% default target with 12-month, multi-year CAGR and every-year definitions.
- Quality evidence and profitability gates, independent of valuation/forward-return assumptions.
- Configurable target-probability and downside limits. Empty results are valid.
- Up to five qualified candidates per sector, plus all scored stocks and exclusion reasons.
- Existing Forward Planning assumptions and risk paths reused for individual stocks.
- Equal-weight joint portfolios of up to 12 qualifying stocks, position/sector caps, yearly RB versus NR, correlations, turnover and downside outcomes.
- Separate Expected Investment Return and Planning Return; neither is a withdrawal-rate promise.
- Background jobs with progress and shared workload guard.
- JSON audit and CSV result downloads; optional immutable paper snapshots saved locally and to the configured GitHub repository when existing permissions allow.
- Offline vintage-frozen stock-screen walk-forward runner, explicit missing outcomes and benchmark gaps.

## Reliability limits

Research release, not a proven profitable strategy. All target probabilities are explicitly uncalibrated and confidence remains low. Point-in-time historical fundamentals, universe/delisting records and benchmark outcomes are not bundled. No actual empirical performance or high-probability certification is claimed. The test runner evaluates the stock-selection screen, not discretionary portfolio choices. A full automatic portfolio optimizer, complete factor model, comprehensive sector-specific accounting model, tax-aware opportunity returns and automated paper-outcome reconciliation are not included.

Read QUALITY_OPPORTUNITIES.md for exact formulas, eligibility, cost timing, timestamps, data requirements and the offline test-bundle schema. Quality uses heuristic sector-relative/absolute metrics; positive ROIC/ROE and operating margins are required, and observed nonpositive nonfinancial cash flow is excluded. These are research constraints, not proof of durable business quality.

## Validation

- Full suite: 704 passed, 72 warnings in 25.35 seconds.
- New tests cover current-universe evaluation, ETFs excluded, missing evidence, empty qualifying sets, profitability gates, historical-winner separation, target definitions, costs, joint probabilities, sector limits, both strategies, future-data exclusion, actual walk-forward execution, paper-record immutability, UI rendering and background completion.
- Synthetic scale test: 60 stocks, 2,000 paths per stock, five years, 30 qualifying sector leaders, and a 12-stock joint RB/NR evaluation completed in 4.48 seconds with peak RSS 130,336 KiB. It used in-memory synthetic source fixtures, permissive constraints and one BLAS thread; this is not a live-data latency or production-capacity promise.
- Existing historical/projection calculation modules are reused; this feature did not change their financial formulas. The prior 5.11.37 deployment/resource changes remain included.

## Deploy and use

1. Merge archive contents into the Stock_ETF-Tracker repository root. Preserve secrets, existing live data, saved simulations and reports.
2. Retain the Render Start Command `python start_marketscope.py` required by 5.11.37, then deploy.
3. Confirm v5.11.38 and open the new tab. Choose thresholds and press Evaluate current stock universe.
4. If current CMA data is unavailable, either refresh its real source or explicitly select and date your Treasury assumption. No hidden fixed-return fallback is used.
5. Read source failures and exclusions before interpreting results. Change constraints only deliberately; the app never relaxes them to fill a list.

This package was not pushed to GitHub or deployed to Render. GitHub currently reported 5.11.36 during this work; 5.11.38 is cumulative from the newer delivered 5.11.37 package.
