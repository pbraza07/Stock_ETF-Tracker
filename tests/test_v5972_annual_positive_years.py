from __future__ import annotations

import ast
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
PDF = (ROOT / "portfolio_simulations.py").read_text(encoding="utf-8")


def _functions(*names):
    tree = ast.parse(APP)
    return [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in set(names)
    ]


def test_release_version_5972():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.11.5"
    assert "v5.11.5" in APP


def test_annual_engine_persists_positive_years_and_years_modeled():
    assert '"positive_years": int(positive_years)' in APP
    assert '"years_modeled": int(len(completed_withdrawal_rows))' in APP
    assert 'float(row.get("portfolio_return_pct") or 0.0) > 0.0' in APP


def test_positive_years_are_based_on_strategy_return_not_withdrawal_success():
    ns = {}
    exec(
        compile(
            ast.Module(
                body=_functions("_annual_withdrawal_positive_year_counts"),
                type_ignores=[],
            ),
            "app.py",
            "exec",
        ),
        ns,
    )
    result = {
        "schedule": [
            {"year": "2021", "portfolio_return_pct": 10.0, "withdrawal": 60000.0},
            {"year": "2022", "portfolio_return_pct": -20.0, "withdrawal": 60000.0},
            {"year": "2023", "portfolio_return_pct": 5.0, "withdrawal": 60000.0},
            {"year": "2024", "portfolio_return_pct": 0.0, "withdrawal": 60000.0},
            {"year": "YTD (partial)", "portfolio_return_pct": 50.0, "withdrawal": 0.0},
        ]
    }
    assert ns["_annual_withdrawal_positive_year_counts"](result) == (2, 4)


def test_live_annual_summary_uses_positive_years():
    live = APP[APP.index("ANNUAL WITHDRAWAL — REBALANCED VS NOT REBALANCED"):]
    assert "_annual_withdrawal_positive_year_counts(" in live
    assert "rb_positive" in live
    assert "nr_positive" in live
    assert "_annual_withdrawal_funding_counts(" not in live.split("if portfolio_monthly_withdrawals_enabled", 1)[0]


def test_save_manage_active_annual_summary_uses_positive_years():
    section = APP.split("SAVE / MANAGE PORTFOLIO SIMULATIONS", 1)[1]
    assert "_manage_rb_positive" in section
    assert "_manage_nr_positive" in section
    assert "_annual_withdrawal_positive_year_counts(" in section


def test_saved_library_card_labels_positive_years():
    names = {
        "_annual_withdrawal_positive_year_counts",
        "_saved_simulation_withdrawal_values",
        "_saved_simulation_withdrawal_inline_html",
    }
    ns = {"escape": escape}
    exec(
        compile(
            ast.Module(body=_functions(*names), type_ignores=[]),
            "app.py",
            "exec",
        ),
        ns,
    )
    record = {
        "annual_withdrawals_enabled": True,
        "annual_withdrawal_amount": 60000.0,
        "annual_positive_years_rebalanced": 15,
        "annual_years_modeled_rebalanced": 17,
        "annual_positive_years_not_rebalanced": 14,
        "annual_years_modeled_not_rebalanced": 17,
        "withdrawal_rebalanced": {"ending_balance": 330029.72},
        "withdrawal_not_rebalanced": {"ending_balance": 429677.41},
    }
    html = ns["_saved_simulation_withdrawal_inline_html"](record)
    assert "POSITIVE YEARS" in html
    assert "WITHDRAWALS FUNDED" not in html
    assert "RB</em> 15/17" in html
    assert "NR</em> 14/17" in html


def test_pdf_page1_uses_positive_years_instead_of_funded():
    assert "POSITIVE YRS RB {rb_pos}/{rb_years} NR {nr_pos}/{nr_years}" in PDF
    assert "FUNDED RB {rb_funded}/{rb_target} NR {nr_funded}/{nr_target}" not in PDF


def test_new_saved_records_persist_positive_year_counts():
    for token in [
        '"annual_positive_years_rebalanced"',
        '"annual_positive_years_not_rebalanced"',
        '"annual_years_modeled_rebalanced"',
        '"annual_years_modeled_not_rebalanced"',
    ]:
        assert token in APP


def test_pdf_contract_bumped_to_v30():
    marker = (
        'MarketScope Portfolio Split Simulator v37 - v5.9.82 monthly reset + monthly start-year RB/NR depletion dashboard + continuous monthly start-year paths + start-year RB/NR depletion dashboard + split start-year strategies + persistent Build Simulation withdrawal tabs + annual and monthly reset views + annual positive years + display-mode searchable dropdowns + six-month universe change history + saved-card inline withdrawal summary + PDF withdrawal summary + Market Table target transcription + required instrument market data on page 1'
    )
    assert APP.count(marker) >= 2
