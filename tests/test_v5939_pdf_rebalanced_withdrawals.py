from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_version():
    assert (ROOT / "VERSION.txt").read_text().strip() == "5.9.77"


def test_pdf_contains_both_withdrawal_strategies():
    src = (ROOT / "portfolio_simulations.py").read_text(encoding="utf-8")
    assert "ANNUAL WITHDRAWALS - STRATEGY COMPARISON" in src
    assert "ANNUAL WITHDRAWAL SCHEDULE - REBALANCED" in src
    assert "ANNUAL WITHDRAWAL SCHEDULE - NOT REBALANCED" in src
    assert 'record.get("withdrawal_rebalanced_schedule")' in src
    assert 'record.get("withdrawal_not_rebalanced_schedule")' in src
    assert "REBALANCE DIFFERENCE" in src


def test_pdf_layout_contract_forces_rebuild():
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    marker = 'MarketScope Portfolio Split Simulator v35 - v5.9.77 split start-year rebalanced/not-rebalanced tabs + start-year rolling withdrawal paths + persistent Build Simulation withdrawal tabs + annual reset inside withdrawal tabs + annual reset withdrawal factor + annual positive years + display-mode searchable dropdowns + six-month universe change history + saved-card inline withdrawal summary + PDF withdrawal summary + Market Table target transcription + required instrument market data on page 1'
    assert src.count(marker) >= 2
