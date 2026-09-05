from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def _load_reset_helpers():
    tree = ast.parse(APP)
    names = {
        "_portfolio_common_calendar_years",
        "_portfolio_annual_reset_dataframe",
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
    return ns["_portfolio_annual_reset_dataframe"]


def test_release_version_5974():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.11.6"
    assert "v5.11.6" in APP


def test_annual_reset_is_inside_build_annual_withdrawal_tabs_not_top_level():
    assert 'portfolio_build_tab, portfolio_manage_tab = st.tabs' in APP
    assert "portfolio_reset_tab" not in APP
    assert '"📅 Annual Reset"' in APP
    annual_section = APP[APP.index("ANNUAL WITHDRAWAL — REBALANCED VS NOT REBALANCED"):]
    assert 'rb_tab, nr_tab, compare_tab, reset_tab, start_year_rb_tab, start_year_nr_tab = st.tabs([' in annual_section
    assert '"⚖ Side-by-side",' in annual_section
    assert '"📅 Annual Reset",' in annual_section
    assert "with reset_tab:" in annual_section


def test_reset_table_starts_with_same_principal_each_year_and_applies_withdrawal():
    build = _load_reset_helpers()
    market = pd.DataFrame([
        {"Symbol": "AAA", "2024": 100.0, "2023": 10.0, "2022": 5.0},
        {"Symbol": "BBB", "2024": 0.0, "2023": 20.0, "2022": np.nan},
    ])
    out = build(
        market,
        ["AAA", "BBB"],
        {"AAA": 50.0, "BBB": 50.0},
        100000.0,
        20000.0,
        ["2024", "2023", "2022"],
    )

    assert out["Year"].tolist() == [2023, 2024]
    assert out["Starting Balance ($)"].tolist() == [100000.0, 100000.0]

    row_2023 = out.loc[out["Year"] == 2023].iloc[0]
    row_2024 = out.loc[out["Year"] == 2024].iloc[0]

    assert row_2023["Annual Return (%)"] == 15.0
    assert round(float(row_2023["Gain / Loss ($)"]), 2) == 15000.0
    assert round(float(row_2023["Before Withdrawal ($)"]), 2) == 115000.0
    assert round(float(row_2023["Withdrawal ($)"]), 2) == 20000.0
    assert round(float(row_2023["Remaining After Withdrawal ($)"]), 2) == 95000.0

    # The next row still resets to the original $100K rather than $95K.
    assert row_2024["Annual Return (%)"] == 50.0
    assert round(float(row_2024["Before Withdrawal ($)"]), 2) == 150000.0
    assert round(float(row_2024["Remaining After Withdrawal ($)"]), 2) == 130000.0


def test_reset_table_restricts_to_current_completed_year_window_and_common_data():
    build = _load_reset_helpers()
    market = pd.DataFrame([
        {"Symbol": "AAA", "2024": 5.0, "2023": 4.0, "2022": 3.0},
        {"Symbol": "BBB", "2024": 6.0, "2023": 2.0, "2022": np.nan},
        {"Symbol": "CCC", "2024": 7.0, "2023": 1.0, "2022": 9.0},
    ])
    out = build(
        market,
        ["AAA", "BBB", "CCC"],
        {"AAA": 34.0, "BBB": 33.0, "CCC": 33.0},
        300000.0,
        70000.0,
        ["2023", "2022"],
    )
    # 2024 is outside the selected window; 2022 is missing BBB; only 2023 survives.
    assert out["Year"].tolist() == [2023]


def test_reset_table_honors_current_custom_allocation_and_withdrawal():
    build = _load_reset_helpers()
    market = pd.DataFrame([
        {"Symbol": "AAA", "2024": 20.0, "2023": -10.0, "2022": 0.0},
        {"Symbol": "BBB", "2024": 0.0, "2023": 10.0, "2022": 0.0},
    ])
    out = build(
        market,
        ["AAA", "BBB"],
        {"AAA": 60.0, "BBB": 40.0},
        200000.0,
        50000.0,
        ["2024", "2023"],
    )
    row_2024 = out.loc[out["Year"] == 2024].iloc[0]
    row_2023 = out.loc[out["Year"] == 2023].iloc[0]

    assert row_2024["Annual Return (%)"] == 12.0
    assert round(float(row_2024["Before Withdrawal ($)"]), 2) == 224000.0
    assert round(float(row_2024["Remaining After Withdrawal ($)"]), 2) == 174000.0

    assert row_2023["Annual Return (%)"] == -2.0
    assert round(float(row_2023["Before Withdrawal ($)"]), 2) == 196000.0
    assert round(float(row_2023["Remaining After Withdrawal ($)"]), 2) == 146000.0


def test_reset_table_caps_actual_withdrawal_and_flags_partial():
    build = _load_reset_helpers()
    market = pd.DataFrame([
        {"Symbol": "AAA", "2024": -90.0, "2023": 10.0, "2022": 0.0},
        {"Symbol": "BBB", "2024": -90.0, "2023": 10.0, "2022": 0.0},
    ])
    out = build(
        market,
        ["AAA", "BBB"],
        {"AAA": 50.0, "BBB": 50.0},
        100000.0,
        70000.0,
        ["2024"],
    )
    row = out.iloc[0]
    assert round(float(row["Before Withdrawal ($)"]), 2) == 10000.0
    assert round(float(row["Withdrawal ($)"]), 2) == 10000.0
    assert round(float(row["Remaining After Withdrawal ($)"]), 2) == 0.0
    assert row["Withdrawal Status"] == "Partial"


def test_reset_table_keeps_per_instrument_returns_and_reference_schedule_columns():
    build = _load_reset_helpers()
    market = pd.DataFrame([
        {"Symbol": "AAA", "2024": 20.0, "2023": 10.0, "2022": 5.0},
        {"Symbol": "BBB", "2024": 5.0, "2023": 6.0, "2022": 7.0},
    ])
    out = build(
        market,
        ["AAA", "BBB"],
        {"AAA": 50.0, "BBB": 50.0},
        100000.0,
        25000.0,
        ["2024", "2023"],
    )
    for col in [
        "Year",
        "Starting Balance ($)",
        "AAA Return (%)",
        "BBB Return (%)",
        "Annual Return (%)",
        "Gain / Loss ($)",
        "Before Withdrawal ($)",
        "Withdrawal ($)",
        "Remaining After Withdrawal ($)",
        "Withdrawal Status",
    ]:
        assert col in out.columns


def test_reset_tab_uses_current_simulator_withdrawal_and_effective_years():
    annual_section = APP[APP.index("ANNUAL WITHDRAWAL — REBALANCED VS NOT REBALANCED"):]
    reset_section = annual_section[annual_section.index("with reset_tab:"):]
    assert "float(portfolio_total)" in reset_section
    assert "float(portfolio_annual_withdrawal)" in reset_section
    assert "list(effective_portfolio_years)" in reset_section
    assert "Withdrawal occurs after that year's return." in reset_section


def test_pdf_contract_bumped_to_v32():
    marker = 'MarketScope Portfolio Split Simulator v37 - v5.9.82 monthly reset + monthly start-year RB/NR depletion dashboard + continuous monthly start-year paths + start-year RB/NR depletion dashboard + split start-year strategies + persistent Build Simulation withdrawal tabs + annual and monthly reset views + annual positive years + display-mode searchable dropdowns + six-month universe change history + saved-card inline withdrawal summary + PDF withdrawal summary + Market Table target transcription + required instrument market data on page 1'
    assert APP.count(marker) >= 2
