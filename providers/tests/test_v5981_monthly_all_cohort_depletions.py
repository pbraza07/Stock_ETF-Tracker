from __future__ import annotations

import ast
from html import escape
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
CSS = (ROOT / "styles.css").read_text(encoding="utf-8")


def _load_helpers():
    tree = ast.parse(APP)
    names = {"_monthly_start_year_depletion_summary", "_monthly_depletion_card_html"}
    nodes = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    namespace = {"pd": pd, "escape": escape}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "app.py", "exec"), namespace)
    return namespace


def test_monthly_summary_includes_every_cohort_start_and_depletion_month():
    summarize = _load_helpers()["_monthly_start_year_depletion_summary"]
    frame = pd.DataFrame([
        {"Start Year": 2018, "Month": "2018-01", "Remaining After Withdrawal ($)": 100000.0},
        {"Start Year": 2018, "Month": "2020-04", "Remaining After Withdrawal ($)": 0.0},
        {"Start Year": 2019, "Month": "2019-01", "Remaining After Withdrawal ($)": 90000.0},
        {"Start Year": 2019, "Month": "2020-02", "Remaining After Withdrawal ($)": 0.0},
        {"Start Year": 2020, "Month": "2020-01", "Remaining After Withdrawal ($)": 80000.0},
        {"Start Year": 2020, "Month": "2020-12", "Remaining After Withdrawal ($)": 50000.0},
    ])
    result = summarize(frame)
    assert result["cohort_outcomes"] == [
        {"start_year": 2018, "start_period": "2018-01", "depletion_period": "2020-04", "last_period": "2020-04"},
        {"start_year": 2019, "start_period": "2019-01", "depletion_period": "2020-02", "last_period": "2020-02"},
        {"start_year": 2020, "start_period": "2020-01", "depletion_period": None, "last_period": "2020-12"},
    ]


def test_monthly_card_places_all_cohort_dates_inside_the_border():
    render = _load_helpers()["_monthly_depletion_card_html"]
    html = render("RB first depletion month", {
        "total_cohorts": 2,
        "depleted_cohorts": 1,
        "first_depletion_period": "2020-04",
        "first_depletion_start_year": 2018,
        "cohort_outcomes": [
            {"start_period": "2018-01", "depletion_period": "2020-04", "last_period": "2020-04"},
            {"start_period": "2019-01", "depletion_period": None, "last_period": "2025-12"},
        ],
    })
    assert html.startswith('<div class="monthly-depletion-detail-card">')
    assert "Initiated <b>2018-01</b>" in html
    assert "Depleted <b>2020-04</b>" in html
    assert "Initiated <b>2019-01</b>" in html
    assert "Not depleted through <b>2025-12</b>" in html
    assert html.endswith("</div>")


def test_monthly_depletion_cards_are_responsive_and_keep_two_strategy_columns():
    section = APP[APP.index("def _render_monthly_start_year_depletion_dashboard()") :]
    section = section[: section.index("def _render_monthly_start_year_paths_tab(")]
    assert "dep_rb_col, dep_nr_col = st.columns(2)" in section
    assert "_monthly_depletion_card_html(_label, _summary)" in section
    assert ".monthly-depletion-detail-card" in CSS
    assert ".monthly-depletion-cohort-grid" in CSS
    assert "@media (max-width: 620px)" in CSS
