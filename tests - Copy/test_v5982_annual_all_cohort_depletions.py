from __future__ import annotations

import ast
from html import escape
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def _load_helpers():
    tree = ast.parse(APP)
    names = {"_start_year_depletion_summary", "_annual_depletion_card_html"}
    nodes = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    namespace = {"pd": pd, "escape": escape}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "app.py", "exec"), namespace)
    return namespace


def test_annual_summary_includes_every_cohort_start_and_depletion_year():
    summarize = _load_helpers()["_start_year_depletion_summary"]
    frame = pd.DataFrame([
        {"Start Year": 2015, "Year": 2015, "Remaining After Withdrawal ($)": 100000.0},
        {"Start Year": 2015, "Year": 2020, "Remaining After Withdrawal ($)": 0.0},
        {"Start Year": 2017, "Year": 2017, "Remaining After Withdrawal ($)": 90000.0},
        {"Start Year": 2017, "Year": 2022, "Remaining After Withdrawal ($)": 0.0},
        {"Start Year": 2019, "Year": 2019, "Remaining After Withdrawal ($)": 80000.0},
        {"Start Year": 2019, "Year": 2025, "Remaining After Withdrawal ($)": 50000.0},
    ])
    result = summarize(frame)
    assert result["cohort_outcomes"] == [
        {"start_year": 2015, "start_period": 2015, "depletion_year": 2020, "last_year": 2020},
        {"start_year": 2017, "start_period": 2017, "depletion_year": 2022, "last_year": 2022},
        {"start_year": 2019, "start_period": 2019, "depletion_year": None, "last_year": 2025},
    ]


def test_annual_card_keeps_all_years_inside_and_has_no_outside_caption():
    render = _load_helpers()["_annual_depletion_card_html"]
    html = render("RB first depletion year", {
        "total_cohorts": 2,
        "depleted_cohorts": 1,
        "first_depletion_year": 2020,
        "first_depletion_start_year": 2015,
        "cohort_outcomes": [
            {"start_period": 2015, "depletion_year": 2020, "last_year": 2020},
            {"start_period": 2017, "depletion_year": None, "last_year": 2025},
        ],
    })
    assert html.startswith('<div class="monthly-depletion-detail-card annual-depletion-detail-card">')
    assert "Initiated <b>2015</b>" in html
    assert "Depleted <b>2020</b>" in html
    assert "Initiated <b>2017</b>" in html
    assert "Not depleted through <b>2025</b>" in html

    section = APP[APP.index("def _render_start_year_depletion_dashboard()") :]
    section = section[: section.index("def _render_start_year_paths_tab(")]
    assert "_annual_depletion_card_html(_label, _summary)" in section
    assert "_col.caption" not in section
    assert "_col.metric" not in section


def test_annual_and_monthly_cards_use_the_same_responsive_cohort_structure():
    assert "ALL COHORT START AND DEPLETION YEARS" in APP
    assert "ALL COHORT START AND DEPLETION MONTHS" in APP
    assert 'class="monthly-depletion-cohort-grid"' in APP
