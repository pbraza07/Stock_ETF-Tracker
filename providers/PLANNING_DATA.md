# Data and model contract

All returns/rates in planning JSON are decimal fractions. Dollar inputs are nominal USD. The annual withdrawal input is desired NET spending when taxes are enabled. Monthly cash flows use beginning/end timing and an annual inflation anniversary. Spending is not assumed funded merely because final wealth is positive.

## Forward CMA configuration
FRED treasury_10y supplies the current rate where available. Optional cma_inputs: as_of, treasury_yield, inflation_expectation, forward_pe, normalized_pe, earnings_growth, dividend_yield, valuation_percentile, long_run_market_return, history_source, institutional (array of source/as_of/return). Institutional returns must be comparable nominal geometric U.S. equity forecasts; normalize horizons/currencies before entry. No vendor ensemble is invented when absent. ERP and normalized real growth are configurable policy assumptions, not downloaded facts. Valuation uses dividend + earnings growth + annualized multiple convergence; earnings yield is exposed to avoid adding it again and double-counting distributions. Current implementation reports valuation percentile if supplied, without a second valuation adjustment.

Source dates entered by users are assertions, not verified vendor publication dates. Missing source dates are displayed. CMA sensitivity range is not a calibrated statistical confidence interval. New Forward Planning contains no permanent 7% anchor. Legacy engine retains its old assumptions solely for compatibility and reproduction; select it explicitly.

## Point-in-time bundle
Run `python planning_backtest.py bundle.json output.json`. No network calls or present-day source data are used by the runner.

Bundle keys: records, cutoffs (year-end historical dates), horizons [1,3,5,10], holding_count, simulation_count, verified_delisted_coverage, realized_annual_returns. Each record has kind, key, observation_date, available_at, value. Each revised vintage is a separate row. Kinds:
- universe: ticker key; value {eligible: true, sector: "...", name: "..."}; point-in-time membership must include failed firms.
- prices: ticker key; completed annual total return as decimal; observation_date identifies December 31. Do not label daily prices as annual returns.
- sectors: ticker key; sector label as known then.
- fundamentals: ticker key; dictionary of forward_pe, earnings_growth, operating_margin, debt_to_equity (percent units), return_on_equity, etc. Every field must have been published by available_at.
- macro: configured macro key (e.g. treasury_10y); raw series value (Treasury percentage units).

realized_annual_returns maps ticker -> year -> decimal total return. It is exposed only to the outcome evaluator, not selection/forecast. Include delisting returns and subsequent cash-slot treatment. Missing future outcomes are skipped, never filled with surviving peers. FULL integrity describes supplied schema coverage; certify source vintages independently. Do not set verified_delisted_coverage unless complete terminal events/membership are verified. This repo does not supply such a dataset. Current app therefore reports LIMITED / UNVALIDATED by default.

Import completed records through planning overrides validation_records; include verified_point_in_time_manifest only after external provenance review. Correction uses only completed, FULL, survivorship-complete one-year tests, minimum 10 nonoverlapping periods, bounded to +/-3 percentage points. Forecast bias = realized CAGR minus P50; negative means the model overpredicted. Supplied records must match this model version and return/cost convention.

## Model policies and limitations
Nine structural scenarios and their transition probabilities are user-overridable stress design assumptions, not estimated forecasts. Regime return shifts summarize earnings/multiple/macroeconomic effects. Block lengths randomly mix 3/6/12/24 months only where contiguous observed monthly data exist. Without such history bootstrap weight moves to Monte Carlo, with an explicit diagnostic. Historical-Calibrated remains the separate uncentered historical-scenario mode.

Student-t log shocks are truncated for finite moments/numerical safety. Monthly gaps and permanent impairment are assumptions; failed slots retain recovery cash with zero return, no automatic replacement stock. Structural and impairment calibration has not been empirically established. Longer horizons increase parameter uncertainty and reduce signal weights; constant normalized fundamentals do not force a declining return schedule.

Taxes are average-cost estimates. Blended account shares apply uniformly, without tax-lot management. No capital loss credits, brackets, early withdrawal penalties, qualified-dividend calculations or tax law forecasting. PAL interest is paid from portfolio or capitalized; taxes/friction affect mandatory repayments. Initial PAL cash proceeds are external, not added to assets. Monthly maintenance checks cannot capture intraday lender calls. Rebalancing tax is applied only to taxable account share; internal deferred/Roth trades are not taxed.

Expected Investment Return is first-year weighted geometric economic drift before impairment/gaps/costs, not promised portfolio CAGR. Arithmetic return is the average first-year compounded per-security sample; median CAGR is from no-withdrawal reference paths. Planning Return is a lower terminal-CAGR percentile, reduced when model medians disagree. Solver uses widened full paths, a disclosed subset, identical random paths for every trial and a joint funded-and-positive-equity success event. It is not a guaranteed or lifetime mortality-based income rate. Lifetime-style planning means choosing a finite horizon (up to 50 years), not modeling death probabilities.

Stress recovery is to starting account equity after spending; drawdowns include spending. Synthetic stress templates are illustrative, not exact historical replays. No statistically verified 'worst historical stress' is available without return-series replay for the actual portfolio; the UI shows worst illustrative stress instead.
