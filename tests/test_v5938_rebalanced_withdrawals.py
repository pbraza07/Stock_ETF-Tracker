from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]


def test_release_version():
    assert (ROOT / "VERSION.txt").read_text().strip() == "5.9.73"


def test_withdrawal_engine_supports_rebalancing():
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "rebalance_after_withdrawal: bool = False" in src
    assert '"strategy": "Rebalanced annually" if rebalance_after_withdrawal else "Not rebalanced"' in src
    assert "balances[sym] = ending_balance * target_weight" in src


def test_ui_renders_both_withdrawal_strategies():
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "ANNUAL WITHDRAWAL — REBALANCED VS NOT REBALANCED" in src
    assert 'st.tabs(["↻ Rebalanced annually", "↝ Not rebalanced", "⚖ Side-by-side"])' in src
    assert "Rebalanced remaining" in src
    assert "Not rebalanced remaining" in src
    assert "Rebalance difference" in src


def test_saved_record_persists_both_schedules():
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert '"withdrawal_not_rebalanced_schedule"' in src
    assert '"withdrawal_rebalanced_schedule"' in src
    assert '"withdrawal_not_rebalanced"' in src
    assert '"withdrawal_rebalanced"' in src


def test_rebalanced_and_not_rebalanced_paths_diverge_numerically():
    import pandas as pd
    import numpy as np
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_portfolio_annual_withdrawal_schedule")
    module = ast.Module(body=[fn], type_ignores=[])
    ns = {"pd": pd, "np": np, "YEAR_RETURN_COLS": [str(y) for y in range(2025, 2005, -1)], "ANNUAL_HISTORY_YEARS": 20}
    exec(compile(module, "app.py", "exec"), ns)
    run = ns["_portfolio_annual_withdrawal_schedule"]
    market = pd.DataFrame([
        {"Symbol": "AAA", "2024": 100.0, "2025": 100.0},
        {"Symbol": "BBB", "2024": 0.0, "2025": 0.0},
    ])
    args = (market, ["AAA", "BBB"], {"AAA": 50.0, "BBB": 50.0}, 100000.0, "2Y", False, 10000.0)
    drift = run(*args, rebalance_after_withdrawal=False)
    reb = run(*args, rebalance_after_withdrawal=True)
    assert not drift["unavailable"] and not reb["unavailable"]
    assert drift["strategy"] == "Not rebalanced"
    assert reb["strategy"] == "Rebalanced annually"
    assert round(drift["ending_balance"], 2) != round(reb["ending_balance"], 2)
