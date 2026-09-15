from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_total_profit_sort_is_available_and_uses_investment_inputs():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert '"Total Profit ($)"' in app
    assert 'sort_choice == "Total Profit ($)"' in app
    assert '_investment_projection_for_sort(row, investment_amount, include_current_ytd, investment_years)' in app
    assert '.get("profit", np.nan)' in app


def test_version_is_current_upgrade():
    assert tuple(map(int, (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip().split("."))) >= (5, 9, 8)
