from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def _load_helpers():
    tree = ast.parse(APP)
    names = {
        "_portfolio_common_calendar_years",
        "_portfolio_annual_withdrawal_schedule",
        "_portfolio_start_year_paths_dataframe",
    }
    nodes = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    ns = {
        "pd": pd,
        "np": np,
        "YEAR_RETURN_COLS": ["2024", "2023", "2022"],
        "ANNUAL_HISTORY_YEARS": 3,
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "app.py", "exec"), ns)
    return ns["_portfolio_start_year_paths_dataframe"]


def test_release_version_5977():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.10.1"
    assert "v5.10.1" in APP


def test_start_year_strategies_are_separate_tabs():
    assert APP.count('"📈 Start-Year Rebalanced"') >= 2
    assert APP.count('"📉 Start-Year Not Rebalanced"') >= 2
    assert '"📈 Start-Year Paths"' not in APP

    success = APP[APP.index("annual_withdrawal_tabs_rendered = False"):]
    success = success[:success.index("if not annual_withdrawal_tabs_rendered:")]
    assert (
        "rb_tab, nr_tab, compare_tab, reset_tab, start_year_rb_tab, start_year_nr_tab = st.tabs(["
        in success
    )
    assert "with start_year_rb_tab:" in success
    assert "with start_year_nr_tab:" in success


def test_rebalanced_start_year_path_rolls_balance_forward():
    build = _load_helpers()
    market = pd.DataFrame([
        {"Symbol": "AAA", "2024": 10.0, "2023": 10.0, "2022": 10.0},
        {"Symbol": "BBB", "2024": 10.0, "2023": 10.0, "2022": 10.0},
    ])
    out = build(
        market,
        ["AAA", "BBB"],
        {"AAA": 50.0, "BBB": 50.0},
        100000.0,
        20000.0,
        ["2024", "2023", "2022"],
        True,
    )

    assert "Strategy" not in out.columns
    cohort = out[out["Start Year"] == 2022].reset_index(drop=True)
    assert cohort["Year"].tolist() == [2022, 2023, 2024]
    assert round(float(cohort.loc[0, "Starting Balance ($)"]), 2) == 100000.00
    assert round(float(cohort.loc[0, "Remaining After Withdrawal ($)"]), 2) == 90000.00
    assert round(float(cohort.loc[1, "Starting Balance ($)"]), 2) == 90000.00
    assert round(float(cohort.loc[1, "Remaining After Withdrawal ($)"]), 2) == 79000.00


def test_not_rebalanced_path_is_calculated_independently():
    build = _load_helpers()
    market = pd.DataFrame([
        {"Symbol": "AAA", "2024": 50.0, "2023": 100.0, "2022": 0.0},
        {"Symbol": "BBB", "2024": 0.0, "2023": 0.0, "2022": 0.0},
    ])
    weights = {"AAA": 50.0, "BBB": 50.0}

    rb = build(market, ["AAA", "BBB"], weights, 100000.0, 10000.0, ["2024","2023","2022"], True)
    nr = build(market, ["AAA", "BBB"], weights, 100000.0, 10000.0, ["2024","2023","2022"], False)

    rb_cohort = rb[rb["Start Year"] == 2022].reset_index(drop=True)
    nr_cohort = nr[nr["Start Year"] == 2022].reset_index(drop=True)

    # First year matches because both start at the target allocation.
    assert round(float(rb_cohort.loc[0, "Remaining After Withdrawal ($)"]), 2) == round(
        float(nr_cohort.loc[0, "Remaining After Withdrawal ($)"]), 2
    )
    # After AAA strongly outperforms, Not Rebalanced drifts and subsequent path diverges.
    assert round(float(rb_cohort.loc[2, "Remaining After Withdrawal ($)"]), 2) != round(
        float(nr_cohort.loc[2, "Remaining After Withdrawal ($)"]), 2
    )


def test_profit_and_profit_percent_include_withdrawn_cash():
    build = _load_helpers()
    market = pd.DataFrame([
        {"Symbol": "AAA", "2024": 10.0, "2023": 10.0, "2022": 10.0},
        {"Symbol": "BBB", "2024": 10.0, "2023": 10.0, "2022": 10.0},
    ])
    out = build(
        market,
        ["AAA", "BBB"],
        {"AAA": 50.0, "BBB": 50.0},
        100000.0,
        20000.0,
        ["2024", "2023", "2022"],
        True,
    )
    row = out[(out["Start Year"] == 2022) & (out["Year"] == 2023)].iloc[0]
    assert round(float(row["Cumulative Withdrawn ($)"]), 2) == 40000.00
    assert round(float(row["Profit ($)"]), 2) == 19000.00
    assert round(float(row["Profit (%)"]), 2) == 19.00


def test_table_has_no_strategy_column_because_tabs_are_separate():
    helper_start = APP.index("def _portfolio_start_year_paths_dataframe")
    helper_end = APP.index("def _portfolio_monthly_withdrawal_schedule", helper_start)
    helper = APP[helper_start:helper_end]
    assert '"Strategy"' not in helper
    for token in [
        '"Start Year"',
        '"Year"',
        '"Profit ($)"',
        '"Profit (%)"',
        '"Withdrawal ($)"',
        '"Remaining After Withdrawal ($)"',
    ]:
        assert token in helper


def test_fallback_keeps_both_start_year_tabs_visible():
    fallback = APP[APP.index("if not annual_withdrawal_tabs_rendered:"):]
    assert (
        "rb_tab, nr_tab, compare_tab, reset_tab, start_year_rb_tab, start_year_nr_tab = st.tabs(["
        in fallback
    )
    assert '"📈 Start-Year Rebalanced"' in fallback
    assert '"📉 Start-Year Not Rebalanced"' in fallback
    assert "with start_year_rb_tab:" in fallback
    assert "with start_year_nr_tab:" in fallback


def test_pdf_contract_bumped_to_v35():
    marker = 'MarketScope Portfolio Split Simulator v37 - v5.9.82 monthly reset + monthly start-year RB/NR depletion dashboard + continuous monthly start-year paths + start-year RB/NR depletion dashboard + split start-year strategies + persistent Build Simulation withdrawal tabs + annual and monthly reset views + annual positive years + display-mode searchable dropdowns + six-month universe change history + saved-card inline withdrawal summary + PDF withdrawal summary + Market Table target transcription + required instrument market data on page 1'
    assert APP.count(marker) >= 2
