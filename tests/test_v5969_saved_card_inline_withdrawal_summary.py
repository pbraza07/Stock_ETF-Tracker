from __future__ import annotations

import ast
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
CSS = (ROOT / "styles.css").read_text(encoding="utf-8")


def _helpers():
    names = {
        "_annual_withdrawal_positive_year_counts",
        "_saved_simulation_withdrawal_values",
        "_saved_simulation_withdrawal_inline_html",
    }
    tree = ast.parse(APP)
    return [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]


def _namespace():
    ns = {"escape": escape}
    exec(compile(ast.Module(body=_helpers(), type_ignores=[]), "app.py", "exec"), ns)
    return ns


def test_release_version_5969():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.78"
    assert "v5.9.78" in APP


def test_saved_withdrawal_strip_is_inside_same_library_card():
    card_start = APP.index('"<div class=\'simulation-library-card\'>"')
    card_end = APP.index('"</div>",', card_start)
    card_block = APP[card_start:card_end]
    assert "_saved_withdrawal_inline" in card_block
    assert 'f"{_saved_withdrawal_inline}"' in card_block

    render_pos = APP.index("_saved_withdrawal_inline = _saved_simulation_withdrawal_inline_html(rec)")
    card_pos = APP.index('"<div class=\'simulation-library-card\'>"', render_pos)
    action_pos = APP.index("action_cols = st.columns", card_pos)
    assert render_pos < card_pos < action_pos


def test_old_separate_saved_withdrawal_section_is_removed():
    library = APP[APP.index("for rec in saved_simulations:"):APP.index("with market_tab:")]
    assert "_saved_withdrawal_title" not in library
    assert "saved-withdrawal-summary-title" not in library
    assert "saved-withdrawal-summary-title" not in CSS


def test_inline_yearly_values_match_requested_fields():
    ns = _namespace()
    record = {
        "annual_withdrawals_enabled": True,
        "annual_withdrawal_amount": 160000.0,
        "annual_positive_years_rebalanced": 15,
        "annual_years_modeled_rebalanced": 17,
        "annual_positive_years_not_rebalanced": 14,
        "annual_years_modeled_not_rebalanced": 17,
        "withdrawal_rebalanced": {"ending_balance": 322183.27},
        "withdrawal_not_rebalanced": {"ending_balance": 2471190.68},
    }
    html = ns["_saved_simulation_withdrawal_inline_html"](record)
    assert "ANNUAL WITHDRAWAL" in html
    assert "$160,000.00" in html
    assert "REBALANCED REMAINING" in html
    assert "$322,183.27" in html
    assert "NOT-REBALANCED REMAINING" in html
    assert "$2,471,190.68" in html
    assert "REBALANCE DIFFERENCE" in html
    assert "$-2,149,007.41" in html
    assert "POSITIVE YEARS" in html
    assert "RB</em> 15/17" in html
    assert "NR</em> 14/17" in html


def test_inline_monthly_values_match_requested_fields():
    ns = _namespace()
    record = {
        "monthly_withdrawals_enabled": True,
        "monthly_withdrawal_amount": 9000.0,
        "monthly_positive_months_rebalanced": 81,
        "monthly_positive_months_not_rebalanced": 79,
        "monthly_months_modeled_rebalanced": 120,
        "monthly_months_modeled_not_rebalanced": 120,
        "monthly_withdrawal_rebalanced": {"ending_balance": 1168547.21},
        "monthly_withdrawal_not_rebalanced": {"ending_balance": 2310811.18},
    }
    html = ns["_saved_simulation_withdrawal_inline_html"](record)
    assert "MONTHLY WITHDRAWAL" in html
    assert "$9,000.00" in html
    assert "$1,168,547.21" in html
    assert "$2,310,811.18" in html
    assert "$-1,142,263.97" in html
    assert "POSITIVE MONTHS" in html
    assert "RB</em> 81/120" in html
    assert "NR</em> 79/120" in html


def test_inline_saved_values_use_smaller_font_than_primary_library_metrics():
    assert ".simulation-library-metric b" in CSS
    assert "font-size: .92rem;" in CSS
    assert ".simulation-library-withdrawal-metric b" in CSS
    assert "font-size: .76rem;" in CSS


def test_inline_strip_matches_red_arrow_location_under_primary_metrics():
    assert ".simulation-library-withdrawal-strip" in CSS
    assert "grid-column: 2 / -1;" in CSS
    assert "grid-template-columns: repeat(5, minmax(0, 1fr));" in CSS
    assert "border-top: 1px solid rgba(104,215,255,.10);" in CSS


def test_pdf_contract_bumped_to_v27():
    marker = (
        'MarketScope Portfolio Split Simulator v36 - v5.9.78 start-year RB/NR depletion dashboard + split start-year rebalanced/not-rebalanced tabs + start-year rolling withdrawal paths + persistent Build Simulation withdrawal tabs + annual reset inside withdrawal tabs + annual reset withdrawal factor + annual positive years + display-mode searchable dropdowns + six-month universe change history + saved-card inline withdrawal summary + PDF withdrawal summary + Market Table target transcription + required instrument market data on page 1'
    )
    assert APP.count(marker) >= 2
