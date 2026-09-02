from pathlib import Path
import ast
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
PDF = (ROOT / "portfolio_simulations.py").read_text(encoding="utf-8")


def _load_schedule_function():
    tree = ast.parse(APP)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_portfolio_annual_withdrawal_schedule")
    module = ast.Module(body=[fn], type_ignores=[])
    ns = {"pd": pd, "np": np, "YEAR_RETURN_COLS": [str(y) for y in range(2025, 2005, -1)], "ANNUAL_HISTORY_YEARS": 20}
    exec(compile(module, "app.py", "exec"), ns)
    return ns["_portfolio_annual_withdrawal_schedule"]


def test_release_version_is_5928():
    assert (ROOT / "VERSION.txt").read_text().strip() == "5.9.67"


def test_withdrawal_ui_and_persistence_contract_present():
    assert '"Yearly withdrawal"' in APP
    assert '"Withdrawal / year ($)"' in APP
    assert 'ANNUAL WITHDRAWAL — REBALANCED VS NOT REBALANCED' in APP
    assert '"Remaining After Withdrawal"' in APP
    assert '"annual_withdrawals_enabled"' in APP
    assert '"withdrawal_schedule"' in APP
    assert 'MarketScope Portfolio Split Simulator v25 - v5.9.66 end-to-end analyst target restore + manual universe refresh + responsive withdrawal KPI layout + required instrument market data on page 1' in APP
    assert 'ANNUAL WITHDRAWALS - STRATEGY COMPARISON' in PDF


def test_schedule_applies_return_then_withdrawal_oldest_to_newest():
    fn = _load_schedule_function()
    market = pd.DataFrame([
        {"Symbol": "AAA", "2024": 10.0, "2025": 20.0, "YTD": 5.0},
        {"Symbol": "BBB", "2024": 0.0, "2025": 0.0, "YTD": 5.0},
    ])
    out = fn(market, ["AAA", "BBB"], {"AAA": 50.0, "BBB": 50.0}, 100000.0, "2Y", False, 10000.0)
    assert not out["unavailable"]
    assert [r["year"] for r in out["schedule"]] == ["2024", "2025"]
    # 2024: 50k*1.10 + 50k = 105k; withdraw 10k => 95k.
    assert round(out["schedule"][0]["balance_before_withdrawal"], 2) == 105000.00
    assert round(out["schedule"][0]["ending_balance"], 2) == 95000.00
    # Withdrawal is proportional, so balances become 49,761.90 and 45,238.10.
    # 2025 then applies +20% to AAA, 0% to BBB before the second 10k withdrawal.
    assert round(out["schedule"][1]["ending_balance"], 2) == 94952.38
    assert round(out["total_withdrawn"], 2) == 20000.00
    assert round(out["ending_balance"], 2) == 94952.38


def test_ytd_partial_row_has_no_extra_withdrawal():
    fn = _load_schedule_function()
    market = pd.DataFrame([{"Symbol": "AAA", "2025": 10.0, "YTD": 5.0}])
    out = fn(market, ["AAA"], {"AAA": 100.0}, 100000.0, "1Y", True, 10000.0)
    assert [r["year"] for r in out["schedule"]] == ["2025", "YTD (partial)"]
    assert out["schedule"][-1]["withdrawal"] == 0.0
    assert round(out["ending_balance"], 2) == 105000.00
