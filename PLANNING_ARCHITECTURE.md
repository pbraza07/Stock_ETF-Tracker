# Future Projection upgrade: pre-change inspection and design (A-G)

Baseline: MarketScope 5.11.34. Source inspected before implementation.

## A. Current-state architecture
future_projection.py normalizes inputs, prepares historical means/covariances, runs regime Monte Carlo/bootstrap/factor paths and RB/NR cash-flow accounting. future_projection_live.py loads supplemental data, conditions assumptions and performs historical validation. future_projection_config.py contains a 7% anchor and 1% expected-return floor. historical_calibration.py samples smoothed joint historical blocks. future_projection_ui.py owns controls, caches and displays; projection_dashboard_pdf.py and future_projection.py own PDF/Excel exports.

## B. Identified weaknesses
Historical stock alpha persists in forward drift; bootstrap replays historical means; current signals persist across horizons. Existing validation does not reconstruct historical selection, fundamentals, membership or delisted outcomes. Thus its numerical scores do not establish unbiased predictive accuracy. Current correlations lack pathwise structural scenarios. Existing cash flows omit taxes, PAL maintenance and permanent impairment. Current nominal withdrawal defaults and large ending balances can obscure spending failure.

## C. Modules to change
Add planning_assumptions.py, planning_paths.py, planning_cashflows.py, planning_validation.py, planning_engine.py, planning_ui.py and planning_exports.py. Integrate through existing projection entry points, input normalization, cache, live loader and UI. Preserve existing historical simulator modules and saved-file schemas.

## D. Proposed calculation architecture
Forward CMA components (dated inputs; missing components excluded and disclosed) -> horizon-dependent security decomposition -> monthly correlated regime paths / centered variable-block bootstrap / factor model -> shared RB/NR ledger -> inflation, taxes, costs, borrowing -> goals, sustainable spending, sequence and structural stresses -> trust and export.

Expected Investment Return is the economic estimate; Planning Return is a lower-percentile no-withdrawal CAGR. Sustainable spending is solved against full cash-flow paths under planning uncertainty, never a constant-P50 annuity. Model coefficients, structural scenarios and impairment hazards are disclosed assumptions, not empirically certified probabilities.

## E. Data requirements
Existing Yahoo fundamentals, observed stock/monthly histories and FRED rates/macroeconomics are reused. User-supplied dated broad-market valuation/growth, equity premium and institutional CMA components are supported; institutional forecasts are not fabricated. Treasury inputs can use FRED. True historical certification requires publication/vintage timestamps, historical universe and sector membership, delisted total returns and terminal corporate-action values. A strict snapshot interface rejects after-cutoff inputs; unavailable historical evidence remains LIMITED and unscored. Tax implementation is estimated average-cost/account-blend accounting, not tax-lot or jurisdictional advice. PAL terms are user assumptions; real lenders may demand repayment sooner.

## F. Migration
New UI runs default to the Forward Planning engine. Historical-Calibrated remains explicitly available as historical scenarios. Prior engine remains for compatibility/reproduction and ranking callers; its 7% assumption is labeled legacy and is not used by Forward Planning. Saved historical simulations and other screens are untouched. All new planning assumptions are part of the cache key and audit. Missing critical forward evidence produces an actionable message or explicitly entered assumption, never a hidden 7% final anchor. Version 5.11.35.

## G. Automated validation
Financial tests A-L: historical winners do not set forward means; valuation can detract; deterioration can make returns negative; horizon prefix invariance; Year-20 momentum zero; spending inflation; tax netting; sequence risk; stress correlation; NR proportional sales; percentile wording; cutoff isolation. Additional tests: tax/basis conservation, depletion, PAL maintenance, solver target, impairment permanence, missing-source labels, export content, unchanged legacy regressions. Visual PDF render check required. Empirical forecasting validation is separate from passing software tests.

Sources: FRED vintage API https://fred.stlouisfed.org/docs/api/fred/series_observations.html ; FINRA SBLOC risk https://www.finra.org/investors/insights/securities-backed-lines-credit ; IRS capital gains https://www.irs.gov/taxtopics/tc409 .
