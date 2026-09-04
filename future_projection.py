"""MarketScope Future Projection percentile enhancements.

v5.10.4 preserves the v5.10.1 Monte Carlo engine in
``future_projection_legacy.py`` and extends the v5.10.2 percentile output with
year-by-year P25/P50/P75 annual return percentages and profit amounts.

All added values are calculated from the exact same Monte Carlo paths already
used by the existing Future Projection engine.
"""

from __future__ import annotations

import numpy as np

import future_projection_legacy as _legacy

# Preserve the complete v5.10.1 module surface, including internal helpers used
# by regression tests and exports. Patched names below intentionally override
# the copied references.
for _name in dir(_legacy):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_legacy, _name)

_original_finish_output_period = _legacy._finish_output_period
_original_finalize_strategy = _legacy._finalize_strategy


def _percentile(values, percentile: float) -> float:
    values = np.asarray(values, dtype=float)
    finite = values[np.isfinite(values)]
    return float(np.percentile(finite, percentile)) if finite.size else 0.0


def _profit_percent(total_wealth_profit, starting_investment: float) -> np.ndarray:
    """Return path-level total-wealth profit as a percent of starting capital.

    Total wealth profit follows MarketScope's existing definition:
    ending balance + withdrawals received - contributions - starting capital.
    """

    starting = float(starting_investment)
    values = np.asarray(total_wealth_profit, dtype=float)
    if not np.isfinite(starting) or starting <= 0:
        return np.zeros_like(values, dtype=float)
    return (values / starting) * 100.0


def _finish_output_period(
    state: dict,
    symbols: list[str],
    starting_investment: float,
    show_month: bool,
) -> None:
    """Add central percentile bands to each annual/monthly output row."""

    acc = state.get("year_accumulator")
    if acc is None:
        return _original_finish_output_period(state, symbols, starting_investment, show_month)

    ending = np.asarray(state["holdings"], dtype=float).sum(axis=1)
    cumulative_withdrawals = np.asarray(state["cumulative_withdrawal"], dtype=float)
    cumulative_contributions = np.asarray(state["cumulative_contribution"], dtype=float)
    cumulative_wealth = ending + cumulative_withdrawals
    total_wealth_profit = (
        cumulative_wealth - cumulative_contributions - float(starting_investment)
    )
    profit_pct = _profit_percent(total_wealth_profit, starting_investment)

    # Gross profit is the exact path-level profit amount accumulated for the
    # displayed period by the authoritative v5.10.1 engine.
    gross_profit = np.asarray(acc["gross"], dtype=float)

    # portfolio_factor is accumulated across the displayed output period, so
    # for annual output this is the path-level annual portfolio return.
    period_return_pct = (np.asarray(acc["portfolio_factor"], dtype=float) - 1.0) * 100.0

    _original_finish_output_period(state, symbols, starting_investment, show_month)

    if not state.get("table_rows"):
        return

    row = state["table_rows"][-1]
    row.update(
        {
            "P25 Gross Profit": _percentile(gross_profit, 25),
            "P50 Gross Profit": _percentile(gross_profit, 50),
            "P75 Gross Profit": _percentile(gross_profit, 75),
            "P25 Ending Balance": _percentile(ending, 25),
            "P50 Ending Balance": _percentile(ending, 50),
            "P75 Ending Balance": _percentile(ending, 75),
            "P25 Cumulative Wealth": _percentile(cumulative_wealth, 25),
            "P50 Cumulative Wealth": _percentile(cumulative_wealth, 50),
            "P75 Cumulative Wealth": _percentile(cumulative_wealth, 75),
            "P25 Total Wealth Profit": _percentile(total_wealth_profit, 25),
            "P50 Total Wealth Profit": _percentile(total_wealth_profit, 50),
            "P75 Total Wealth Profit": _percentile(total_wealth_profit, 75),
            "P25 Profit %": _percentile(profit_pct, 25),
            "P50 Profit %": _percentile(profit_pct, 50),
            "P75 Profit %": _percentile(profit_pct, 75),
            "Profit %": _percentile(profit_pct, 50),
        }
    )

    if show_month:
        row.update(
            {
                "P10 Monthly Return": _percentile(period_return_pct, 10),
                "P25 Monthly Return": _percentile(period_return_pct, 25),
                "P50 Monthly Return": _percentile(period_return_pct, 50),
                "P75 Monthly Return": _percentile(period_return_pct, 75),
                "P90 Monthly Return": _percentile(period_return_pct, 90),
            }
        )
    else:
        row.update(
            {
                "P10 Annual Return": _percentile(period_return_pct, 10),
                "P25 Annual Return": _percentile(period_return_pct, 25),
                "P50 Annual Return": _percentile(period_return_pct, 50),
                "P75 Annual Return": _percentile(period_return_pct, 75),
                "P90 Annual Return": _percentile(period_return_pct, 90),
            }
        )


def _finalize_strategy(
    state: dict,
    no_withdrawal_state: dict | None,
    inputs: dict,
    start_year: int,
    base_monthly: bool,
    model,
) -> dict:
    """Add exact P25/P50/P75 ending and profit percentiles to the summary."""

    ending = np.asarray(state["holdings"], dtype=float).sum(axis=1)
    cumulative_withdrawals = np.asarray(state["cumulative_withdrawal"], dtype=float)
    cumulative_contributions = np.asarray(state["cumulative_contribution"], dtype=float)
    total_wealth_profit = (
        ending
        + cumulative_withdrawals
        - cumulative_contributions
        - float(inputs["starting_investment"])
    )
    profit_pct = _profit_percent(total_wealth_profit, inputs["starting_investment"])

    payload = _original_finalize_strategy(
        state,
        no_withdrawal_state,
        inputs,
        start_year,
        base_monthly,
        model,
    )
    summary = payload.setdefault("summary", {})
    summary.update(
        {
            "P25 Ending Balance": _percentile(ending, 25),
            "P50 Ending Balance": _percentile(ending, 50),
            "P75 Ending Balance": _percentile(ending, 75),
            "P25 Total Wealth Profit": _percentile(total_wealth_profit, 25),
            "P50 Total Wealth Profit": _percentile(total_wealth_profit, 50),
            "P75 Total Wealth Profit": _percentile(total_wealth_profit, 75),
            "P25 Profit %": _percentile(profit_pct, 25),
            "P50 Profit %": _percentile(profit_pct, 50),
            "P75 Profit %": _percentile(profit_pct, 75),
            # User-friendly single Profit % defaults to the P50/median path.
            "Profit %": _percentile(profit_pct, 50),
        }
    )
    return payload


# Patch the legacy module globals used by its original run_future_projection.
# Python resolves these helpers at call time, so the simulation itself remains
# unchanged while the output is enriched from the same raw path arrays.
_legacy._finish_output_period = _finish_output_period
_legacy._finalize_strategy = _finalize_strategy

# Refresh exported references after patching.
_finish_output_period = _legacy._finish_output_period
_finalize_strategy = _legacy._finalize_strategy
run_future_projection = _legacy.run_future_projection
