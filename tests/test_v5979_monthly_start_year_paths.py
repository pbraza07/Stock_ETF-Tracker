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
        "_actual_month_labels",
        "_monthly_year_compound",
        "_monthly_matches_market_table",
        "_portfolio_common_calendar_years",
        "_portfolio_monthly_withdrawal_schedule",
        "_portfolio_monthly_reset_dataframe",
        "_portfolio_monthly_start_year_paths_dataframe",
        "_monthly_start_year_depletion_summary",
    }
    nodes = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    ns = {
        "pd": pd,
        "np": np,
        "YEAR_RETURN_COLS": ["2023", "2022"],
        "ANNUAL_HISTORY_YEARS": 2,
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "app.py", "exec"), ns)
    return ns


def _one_percent_monthly_data():
    labels = [f"{year}-{month:02d}" for year in (2022, 2023) for month in range(1, 13)]
    return {
        "AAA": {label: 0.01 for label in labels},
        "BBB": {label: 0.01 for label in labels},
    }


def _market_for_one_percent_monthly():
    annual = ((1.01 ** 12) - 1.0) * 100.0
    return pd.DataFrame([
        {"Symbol": "AAA", "2023": annual, "2022": annual},
        {"Symbol": "BBB", "2023": annual, "2022": annual},
    ])


def test_release_version_5979():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.11.7"
    assert "v5.11.7" in APP


def test_monthly_start_year_path_carries_balance_across_year_boundary():
    ns = _load_helpers()
    build = ns["_portfolio_monthly_start_year_paths_dataframe"]
    out = build(
        _market_for_one_percent_monthly(),
        ["AAA", "BBB"],
        {"AAA": 50.0, "BBB": 50.0},
        100000.0,
        1000.0,
        ["2023", "2022"],
        True,
        _one_percent_monthly_data(),
    )
    cohort = out[out["Start Year"] == 2022].reset_index(drop=True)
    assert cohort["Month"].tolist()[0] == "2022-01"
    assert cohort["Month"].tolist()[-1] == "2023-12"
    assert len(cohort) == 24
    december = cohort[cohort["Month"] == "2022-12"].iloc[0]
    january = cohort[cohort["Month"] == "2023-01"].iloc[0]
    assert round(float(january["Starting Balance ($)"]), 2) == round(
        float(december["Remaining After Withdrawal ($)"]), 2
    )
    assert round(float(cohort.iloc[-1]["Cumulative Withdrawn ($)"]), 2) == 24000.00
    assert round(float(cohort.iloc[-1]["Profit ($)"]), 2) == 24000.00
    assert round(float(cohort.iloc[-1]["Profit (%)"]), 2) == 24.00


def test_monthly_reset_restarts_the_same_principal_every_row():
    ns = _load_helpers()
    reset = ns["_portfolio_monthly_reset_dataframe"]
    out = reset(
        ["AAA", "BBB"],
        {"AAA": 50.0, "BBB": 50.0},
        100000.0,
        1000.0,
        ["2023", "2022"],
        _one_percent_monthly_data(),
    )
    assert len(out) == 24
    assert out["Starting Balance ($)"].nunique() == 1
    assert float(out["Starting Balance ($)"].iloc[0]) == 100000.0
    assert round(float(out["Remaining After Withdrawal ($)"].iloc[0]), 2) == 100000.00
    assert round(float(out["Remaining After Withdrawal ($)"].iloc[-1]), 2) == 100000.00


def test_monthly_depletion_summary_reports_earliest_month_and_cohort():
    summarize = _load_helpers()["_monthly_start_year_depletion_summary"]
    frame = pd.DataFrame([
        {"Start Year": 2018, "Month": "2020-04", "Remaining After Withdrawal ($)": 0.0},
        {"Start Year": 2019, "Month": "2020-02", "Remaining After Withdrawal ($)": 0.0},
        {"Start Year": 2020, "Month": "2020-12", "Remaining After Withdrawal ($)": 50000.0},
    ])
    result = summarize(frame)
    assert result["total_cohorts"] == 3
    assert result["depleted_cohorts"] == 2
    assert result["first_depletion_period"] == "2020-02"
    assert result["first_depletion_start_year"] == 2019


def test_monthly_tabs_include_reset_and_separate_start_year_strategies():
    for label in [
        '"📅 Monthly Reset"',
        '"📈 Monthly Start-Year Rebalanced"',
        '"📉 Monthly Start-Year Not Rebalanced"',
    ]:
        assert APP.count(label) >= 2
    assert "monthly_withdrawal_tabs_rendered = False" in APP
    assert "if not monthly_withdrawal_tabs_rendered:" in APP
    assert "with mstart_year_rb_tab:" in APP
    assert "with mstart_year_nr_tab:" in APP


def test_monthly_start_year_dashboard_keeps_five_kpis_and_two_depletion_cards():
    section = APP[APP.index("def _render_monthly_start_year_depletion_dashboard()") :]
    section = section[: section.index("for label, result in ((\"Rebalanced\"")]
    assert "dep_rb_col, dep_nr_col = st.columns(2)" in section
    assert "RB first depletion month" in section
    assert "NR first depletion month" in section
    assert "sp1, sp2, sp3, sp4, sp5 = st.columns(5)" in section
    assert 'sp2.metric("Monthly withdrawal"' in section


def test_pdf_contract_bumped_to_v37():
    marker = (
        "MarketScope Portfolio Split Simulator v37 - v5.9.82 monthly reset + monthly start-year RB/NR depletion dashboard + "
        "continuous monthly start-year paths + start-year RB/NR depletion dashboard + split start-year strategies + "
        "persistent Build Simulation withdrawal tabs + annual and monthly reset views + annual positive years + "
        "display-mode searchable dropdowns + six-month universe change history + saved-card inline withdrawal summary + "
        "PDF withdrawal summary + Market Table target transcription + required instrument market data on page 1"
    )
    assert APP.count(marker) >= 2
