from __future__ import annotations

import ast
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
CSS = (ROOT / "styles.css").read_text(encoding="utf-8")


def _load_functions(*names):
    tree = ast.parse(APP)
    nodes = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in set(names)
    ]
    module = ast.Module(body=nodes, type_ignores=[])
    ns = {"escape": escape}
    exec(compile(module, "app.py", "exec"), ns)
    return ns


def test_release_version_5962():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.67"
    assert "v5.9.66" in APP


def test_main_portfolio_summary_no_longer_uses_native_metrics():
    assert 'pc1.metric("Portfolio invested"' not in APP
    assert 'pc2.metric("Calculated ending value"' not in APP
    assert 'pc3.metric("Calculated profit / loss"' not in APP
    assert 'pc4.metric("Calculated return"' not in APP
    assert "def _portfolio_summary_kpi_grid" in APP
    assert "portfolio-summary-kpi-grid" in APP


def test_portfolio_summary_renderer_keeps_all_four_values():
    ns = _load_functions("_portfolio_summary_kpi_grid")
    html = ns["_portfolio_summary_kpi_grid"](
        300000.0, 7366628.0, 7066628.0, 2355.54
    )
    assert "Portfolio invested" in html
    assert "$300,000.00" in html
    assert "$7,366,628.00" in html
    assert "$+7,066,628.00" in html
    assert "+2355.54%" in html


def test_yearly_withdrawal_uses_same_responsive_card_system_as_monthly():
    assert 'wc1.metric("Annual withdrawal"' not in APP
    assert 'wc2.metric("Rebalanced remaining"' not in APP
    assert 'wc3.metric("Not rebalanced remaining"' not in APP
    assert 'wc4.metric("Rebalance difference"' not in APP
    assert "def _annual_withdrawal_kpi_grid" in APP
    assert "monthly-withdrawal-kpi-grid" in APP
    assert "monthly-withdrawal-kpi-card" in APP


def test_yearly_funded_count_excludes_partial_ytd_and_requires_full_payment():
    ns = _load_functions("_annual_withdrawal_funding_counts")
    result = {
        "withdrawals_targeted": 10,
        "withdrawals_funded": 2,
        "schedule": [
            {"year": "2024", "withdrawal": 160000.0},
            {"year": "2025", "withdrawal": 159999.999},
            {"year": "YTD (partial)", "withdrawal": 0.0},
        ],
    }
    funded, target = ns["_annual_withdrawal_funding_counts"](result, 160000.0)
    assert (funded, target) == (2, 10)


def test_yearly_renderer_displays_full_rb_nr_funded_counts():
    ns = _load_functions("_annual_withdrawal_kpi_grid")
    html = ns["_annual_withdrawal_kpi_grid"](
        160000.0, 5618589.40, 1556195.26, 10, 10, 8, 10
    )
    assert "$160,000.00" in html
    assert "$5,618,589.40" in html
    assert "$1,556,195.26" in html
    assert "Withdrawals funded" in html
    assert "RB</em> 10/10" in html
    assert "NR</em> 8/10" in html


def test_mobile_css_is_compact_and_responsive():
    assert ".portfolio-summary-kpi-grid" in CSS
    assert "grid-template-columns: repeat(4, minmax(0, 1fr))" in CSS
    assert "@media (max-width: 1100px)" in CSS
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in CSS
    assert "@media (max-width: 620px)" in CSS
    assert ".portfolio-summary-kpi-card," in CSS
    assert "min-height: 76px" in CSS
    assert "padding: 12px 14px" in CSS


def test_pdf_contract_bumped_to_v21():
    marker = "MarketScope Portfolio Split Simulator v25 - v5.9.66 end-to-end analyst target restore + manual universe refresh + responsive withdrawal KPI layout + required instrument market data on page 1"
    assert APP.count(marker) >= 2
