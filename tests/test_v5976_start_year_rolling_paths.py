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


def test_release_version_5976():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.76"
    assert "v5.9.76" in APP


def test_start_year_paths_is_fifth_tab_beside_annual_reset():
    assert APP.count('"📈 Start-Year Paths"') >= 2
    success = APP[APP.index("annual_withdrawal_tabs_rendered = False"):]
    success = success[:success.index("if not annual_withdrawal_tabs_rendered:")]
    assert 'rb_tab, nr_tab, compare_tab, reset_tab, start_year_tab = st.tabs([' in success
    assert '"📅 Annual Reset",' in success
    assert '"📈 Start-Year Paths",' in success
    assert "with start_year_tab:" in success


def test_each_start_year_begins_fresh_but_subsequent_years_roll_forward():
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
    )

    # Both strategies are included in one table.
    assert set(out["Strategy"]) == {"Rebalanced annually", "Not rebalanced"}

    rb_2022 = out[
        (out["Start Year"] == 2022) &
        (out["Strategy"] == "Rebalanced annually")
    ].reset_index(drop=True)

    assert rb_2022["Year"].tolist() == [2022, 2023, 2024]
    assert round(float(rb_2022.loc[0, "Starting Balance ($)"]), 2) == 100000.00
    assert round(float(rb_2022.loc[0, "Remaining After Withdrawal ($)"]), 2) == 90000.00

    # Subsequent year starts from prior remaining balance, not the original principal.
    assert round(float(rb_2022.loc[1, "Starting Balance ($)"]), 2) == 90000.00
    assert round(float(rb_2022.loc[1, "Remaining After Withdrawal ($)"]), 2) == 79000.00
    assert round(float(rb_2022.loc[2, "Starting Balance ($)"]), 2) == 79000.00
    assert round(float(rb_2022.loc[2, "Remaining After Withdrawal ($)"]), 2) == 66900.00

    # A later cohort starts fresh from the same original investment.
    rb_2023 = out[
        (out["Start Year"] == 2023) &
        (out["Strategy"] == "Rebalanced annually")
    ].reset_index(drop=True)
    assert rb_2023["Year"].tolist() == [2023, 2024]
    assert round(float(rb_2023.loc[0, "Starting Balance ($)"]), 2) == 100000.00


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
    )
    row = out[
        (out["Start Year"] == 2022) &
        (out["Year"] == 2023) &
        (out["Strategy"] == "Rebalanced annually")
    ].iloc[0]

    # Remaining 79K + 40K cumulative withdrawals - 100K initial = 19K profit.
    assert round(float(row["Cumulative Withdrawn ($)"]), 2) == 40000.00
    assert round(float(row["Profit ($)"]), 2) == 19000.00
    assert round(float(row["Profit (%)"]), 2) == 19.00


def test_table_contains_requested_and_audit_columns():
    helper_start = APP.index("def _portfolio_start_year_paths_dataframe")
    helper_end = APP.index("def _portfolio_monthly_withdrawal_schedule", helper_start)
    helper = APP[helper_start:helper_end]
    for token in [
        '"Start Year"',
        '"Year"',
        '"Profit ($)"',
        '"Profit (%)"',
        '"Withdrawal ($)"',
        '"Remaining After Withdrawal ($)"',
        '"Cumulative Withdrawn ($)"',
        '"Starting Balance ($)"',
        '"Annual Return (%)"',
    ]:
        assert token in helper


def test_only_common_eligible_years_are_used():
    build = _load_helpers()
    market = pd.DataFrame([
        {"Symbol": "AAA", "2024": 10.0, "2023": 5.0, "2022": 3.0},
        {"Symbol": "BBB", "2024": 8.0, "2023": np.nan, "2022": 4.0},
    ])
    out = build(
        market,
        ["AAA", "BBB"],
        {"AAA": 50.0, "BBB": 50.0},
        100000.0,
        10000.0,
        ["2024", "2023", "2022"],
    )
    assert 2023 not in set(out["Start Year"])
    assert 2023 not in set(out["Year"])
    assert set(out["Start Year"]) == {2022, 2024}


def test_fallback_keeps_start_year_tab_visible_when_yearly_withdrawal_is_off():
    fallback = APP[APP.index("if not annual_withdrawal_tabs_rendered:"):]
    assert 'rb_tab, nr_tab, compare_tab, reset_tab, start_year_tab = st.tabs([' in fallback
    assert '"📈 Start-Year Paths"' in fallback
    assert "with start_year_tab:" in fallback
    assert "Enable **Yearly withdrawal** above" in fallback


def test_pdf_contract_bumped_to_v34():
    marker = (
        "MarketScope Portfolio Split Simulator v34 - v5.9.76 start-year rolling withdrawal paths + "
        "persistent Build Simulation withdrawal tabs + annual reset inside withdrawal tabs + "
        "annual reset withdrawal factor + annual positive years + display-mode searchable dropdowns + "
        "six-month universe change history + saved-card inline withdrawal summary + PDF withdrawal summary + "
        "Market Table target transcription + required instrument market data on page 1"
    )
    assert APP.count(marker) >= 2
