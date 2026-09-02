from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
CSS = (ROOT / "styles.css").read_text(encoding="utf-8")


def test_release_version_5967():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.79"


def test_save_manage_repeats_active_annual_withdrawal_kpis():
    section = APP.split("SAVE / MANAGE PORTFOLIO SIMULATIONS", 1)[1]
    assert "ACTIVE ANNUAL WITHDRAWAL SUMMARY" in section
    assert "_annual_withdrawal_kpi_grid(" in section
    assert "portfolio_withdrawal_rebalanced_result" in section
    assert "portfolio_withdrawal_not_rebalanced_result" in section
    assert "_annual_withdrawal_positive_year_counts(" in section


def test_save_manage_repeats_active_monthly_withdrawal_kpis():
    section = APP.split("SAVE / MANAGE PORTFOLIO SIMULATIONS", 1)[1]
    assert "ACTIVE MONTHLY WITHDRAWAL SUMMARY" in section
    assert "_monthly_withdrawal_kpi_grid(" in section
    assert "portfolio_monthly_withdrawal_rebalanced_result" in section
    assert "portfolio_monthly_withdrawal_not_rebalanced_result" in section
    assert 'get("positive_months")' in section
    assert 'get("months_modeled")' in section


def test_saved_library_renders_withdrawal_summary_inside_each_saved_card():
    assert "def _saved_simulation_withdrawal_values(record: dict)" in APP
    assert "def _saved_simulation_withdrawal_inline_html(record: dict)" in APP
    assert "_saved_withdrawal_inline = _saved_simulation_withdrawal_inline_html(rec)" in APP
    assert 'f"{_saved_withdrawal_inline}"' in APP
    assert "simulation-library-withdrawal-strip" in APP
    assert ".simulation-library-withdrawal-strip" in CSS
    # The old separate full-width summary below the card is intentionally gone.
    assert "_saved_withdrawal_title" not in APP
    assert "saved-withdrawal-summary-title" not in APP


def test_new_annual_saved_records_persist_positive_years_for_both_paths():
    for field in [
        '"annual_positive_years_rebalanced"',
        '"annual_positive_years_not_rebalanced"',
        '"annual_years_modeled_rebalanced"',
        '"annual_years_modeled_not_rebalanced"',
    ]:
        assert field in APP


def test_saved_summary_helper_supports_legacy_schedule_derived_counts():
    tree = ast.parse(APP)
    selected = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {
            "_annual_withdrawal_positive_year_counts",
            "_saved_simulation_withdrawal_values",
            "_saved_simulation_withdrawal_kpi",
        }
    ]

    def annual_grid(amount, rb_end, nr_end, rb_funded, rb_target, nr_funded, nr_target):
        return f"annual:{amount}:{rb_end}:{nr_end}:{rb_funded}/{rb_target}:{nr_funded}/{nr_target}"

    def monthly_grid(amount, rb_end, nr_end, rb_positive, rb_months, nr_positive, nr_months):
        return f"monthly:{amount}:{rb_end}:{nr_end}:{rb_positive}/{rb_months}:{nr_positive}/{nr_months}"

    ns = {
        "_annual_withdrawal_kpi_grid": annual_grid,
        "_monthly_withdrawal_kpi_grid": monthly_grid,
    }
    exec(compile(ast.Module(body=selected, type_ignores=[]), "app.py", "exec"), ns)

    annual = {
        "annual_withdrawals_enabled": True,
        "annual_withdrawal_amount": 160000.0,
        "withdrawal_rebalanced": {
            "ending_balance": 322183.27,
            "schedule": [
                {"year": "2006", "portfolio_return_pct": 12.0},
                {"year": "2007", "portfolio_return_pct": -2.0},
            ],
        },
        "withdrawal_not_rebalanced": {
            "ending_balance": 2471190.68,
            "schedule": [
                {"year": "2006", "portfolio_return_pct": 8.0},
                {"year": "2007", "portfolio_return_pct": 5.0},
            ],
        },
    }
    title, html = ns["_saved_simulation_withdrawal_kpi"](annual)
    assert title == "ANNUAL WITHDRAWAL SUMMARY"
    assert "1/2:2/2" in html

    monthly = {
        "monthly_withdrawals_enabled": True,
        "monthly_withdrawal_amount": 5000.0,
        "monthly_positive_months_rebalanced": 81,
        "monthly_positive_months_not_rebalanced": 79,
        "monthly_months_modeled_rebalanced": 120,
        "monthly_months_modeled_not_rebalanced": 120,
        "monthly_withdrawal_rebalanced": {"ending_balance": 1200000.0},
        "monthly_withdrawal_not_rebalanced": {"ending_balance": 2000000.0},
    }
    title, html = ns["_saved_simulation_withdrawal_kpi"](monthly)
    assert title == "MONTHLY WITHDRAWAL SUMMARY"
    assert "81/120:79/120" in html
