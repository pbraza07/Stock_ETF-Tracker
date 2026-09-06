from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def _load_summary():
    tree = ast.parse(APP)
    node = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_start_year_depletion_summary"
    )
    ns = {"pd": pd}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "app.py", "exec"), ns)
    return ns["_start_year_depletion_summary"]


def test_release_version_5978():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.11.8"
    assert "v5.11.8" in APP


def test_depletion_summary_returns_earliest_calendar_depletion_and_start_cohort():
    summarize = _load_summary()
    frame = pd.DataFrame([
        {"Start Year": 2015, "Year": 2015, "Remaining After Withdrawal ($)": 300000.0},
        {"Start Year": 2015, "Year": 2018, "Remaining After Withdrawal ($)": 0.0},
        {"Start Year": 2017, "Year": 2017, "Remaining After Withdrawal ($)": 250000.0},
        {"Start Year": 2017, "Year": 2020, "Remaining After Withdrawal ($)": 0.0},
        {"Start Year": 2019, "Year": 2025, "Remaining After Withdrawal ($)": 100000.0},
    ])
    result = summarize(frame)
    assert result["total_cohorts"] == 3
    assert result["depleted_cohorts"] == 2
    assert result["first_depletion_year"] == 2018
    assert result["first_depletion_start_year"] == 2015


def test_depletion_summary_reports_survival_when_no_cohort_hits_zero():
    summarize = _load_summary()
    frame = pd.DataFrame([
        {"Start Year": 2020, "Year": 2020, "Remaining After Withdrawal ($)": 100000.0},
        {"Start Year": 2020, "Year": 2021, "Remaining After Withdrawal ($)": 50000.0},
        {"Start Year": 2021, "Year": 2021, "Remaining After Withdrawal ($)": 120000.0},
    ])
    result = summarize(frame)
    assert result == {
        "total_cohorts": 2,
        "depleted_cohorts": 0,
        "first_depletion_year": None,
        "first_depletion_start_year": None,
        "cohort_outcomes": [
            {"start_year": 2020, "start_period": 2020, "depletion_year": None, "last_year": 2021},
            {"start_year": 2021, "start_period": 2021, "depletion_year": None, "last_year": 2021},
        ],
    }


def test_depletion_dashboard_uses_two_wide_columns_not_six_kpi_cards():
    assert "def _render_start_year_depletion_dashboard()" in APP
    section = APP[APP.index("def _render_start_year_depletion_dashboard()") :]
    section = section[:section.index("def _render_start_year_paths_tab(")]
    assert "dep_rb_col, dep_nr_col = st.columns(2)" in section
    assert "RB first depletion year" in section
    assert "NR first depletion year" in section
    assert "_annual_depletion_card_html(_label, _summary)" in section
    assert "_col.caption" not in section
    assert "Earliest affected start cohort" in APP
    assert "Depleted cohorts" in APP
    assert "Not depleted" in APP


def test_dashboard_keeps_existing_five_large_metrics_unchanged():
    section = APP[APP.index("def _render_start_year_paths_tab(") :]
    section = section[:section.index("start_year_column_config =")]
    assert "sp1, sp2, sp3, sp4, sp5 = st.columns(5)" in section
    for label in [
        "Initial investment",
        "Annual withdrawal",
        "Start-year cohorts",
        "Earliest / Latest",
        "Path rows",
    ]:
        assert label in section
    assert "_render_start_year_depletion_dashboard()" in section


def test_both_strategy_paths_are_precomputed_for_shared_depletion_comparison():
    assert "start_year_rb_paths_df = _portfolio_start_year_paths_dataframe(" in APP
    assert "start_year_nr_paths_df = _portfolio_start_year_paths_dataframe(" in APP
    assert "start_year_rb_depletion = _start_year_depletion_summary(start_year_rb_paths_df)" in APP
    assert "start_year_nr_depletion = _start_year_depletion_summary(start_year_nr_paths_df)" in APP


def test_pdf_contract_preserved_in_v37():
    marker = (
        "MarketScope Portfolio Split Simulator v37 - v5.9.82 monthly reset + monthly start-year RB/NR depletion dashboard + "
        "continuous monthly start-year paths + start-year RB/NR depletion dashboard + split start-year strategies + "
        "persistent Build Simulation withdrawal tabs + annual and monthly reset views + annual positive years + "
        "display-mode searchable dropdowns + six-month universe change history + "
        "saved-card inline withdrawal summary + PDF withdrawal summary + Market Table target transcription + "
        "required instrument market data on page 1"
    )
    assert APP.count(marker) >= 2
