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


def test_release_version_5973():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.73"
    assert "v5.9.73" in APP


def test_portfolio_simulator_has_annual_reset_workspace_tab():
    assert '"📅 Annual Reset Performance"' in APP
    assert "with portfolio_reset_tab:" in APP
    assert "ANNUAL RESET PERFORMANCE" in APP
    assert "portfolio_annual_reset_performance_table" in APP


def test_reset_table_starts_with_same_principal_every_year_and_never_compounds():
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
    )

    assert out["Year"].tolist() == [2023, 2024]
    assert out["Initial Investment ($)"].tolist() == [100000.0, 100000.0]

    row_2023 = out.loc[out["Year"] == 2023].iloc[0]
    row_2024 = out.loc[out["Year"] == 2024].iloc[0]

    assert row_2023["Portfolio Return (%)"] == 15.0
    assert round(float(row_2023["Ending Value ($)"]), 2) == 115000.0
    assert round(float(row_2023["Profit / Loss ($)"]), 2) == 15000.0

    # If profit rolled forward this would start from $115K and end at $172.5K.
    # The requested reset behavior correctly starts from $100K again.
    assert row_2024["Portfolio Return (%)"] == 50.0
    assert round(float(row_2024["Ending Value ($)"]), 2) == 150000.0
    assert round(float(row_2024["Profit / Loss ($)"]), 2) == 50000.0


def test_reset_table_excludes_any_year_missing_one_selected_instrument_return():
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
    )
    assert out["Year"].tolist() == [2023, 2024]
    assert 2022 not in out["Year"].tolist()


def test_reset_table_honors_current_custom_allocation_each_year():
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
    )
    row_2024 = out.loc[out["Year"] == 2024].iloc[0]
    row_2023 = out.loc[out["Year"] == 2023].iloc[0]
    assert row_2024["Portfolio Return (%)"] == 12.0
    assert round(float(row_2024["Ending Value ($)"]), 2) == 224000.0
    assert row_2023["Portfolio Return (%)"] == -2.0
    assert round(float(row_2023["Ending Value ($)"]), 2) == 196000.0


def test_reset_table_shows_each_selected_instrument_return_for_reference_layout():
    build = _load_reset_helpers()
    market = pd.DataFrame([
        {"Symbol": "AAA", "2024": 20.0, "2023": 10.0, "2022": 5.0},
        {"Symbol": "BBB", "2024": 5.0, "2023": 6.0, "2022": 7.0},
    ])
    out = build(market, ["AAA", "BBB"], {"AAA": 50.0, "BBB": 50.0}, 100000.0)
    assert "AAA Return (%)" in out.columns
    assert "BBB Return (%)" in out.columns
    assert "Portfolio Return (%)" in out.columns
    assert "Ending Value ($)" in out.columns
    assert "Profit / Loss ($)" in out.columns


def test_reset_table_uses_full_common_history_not_selected_compounding_period():
    helper_start = APP.index("def _portfolio_annual_reset_dataframe")
    helper_end = APP.index("def _portfolio_horizon_projection", helper_start)
    helper = APP[helper_start:helper_end]
    assert "_portfolio_common_calendar_years(" in helper
    assert "ANNUAL_HISTORY_YEARS" in helper
    assert "period_choice" not in helper
    assert "portfolio_period" not in helper


def test_pdf_contract_bumped_to_v31():
    marker = (
        'MarketScope Portfolio Split Simulator v31 - v5.9.73 annual reset performance + annual positive years + display-mode searchable dropdowns + six-month universe change history + saved-card inline withdrawal summary + PDF withdrawal summary + Market Table target transcription + required instrument market data on page 1'
    )
    assert APP.count(marker) >= 2
