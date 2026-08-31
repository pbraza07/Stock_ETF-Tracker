from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
APP = (BASE / "app.py").read_text(encoding="utf-8")

FILES = [
    ("top200_profit_generators_5y.csv", 5),
    ("top200_best_worst_year_5y.csv", 5),
    ("top200_profit_generators_10y.csv", 10),
    ("top200_best_worst_year_10y.csv", 10),
]

def test_top200_files_exist_and_have_200_rows():
    for filename, _ in FILES:
        path = BASE / "data" / filename
        assert path.exists(), filename
        df = pd.read_csv(path)
        assert len(df) == 200
        assert list(df["Rank"]) == list(range(1, 201))

def test_every_combo_has_four_stocks_from_four_different_sectors():
    for filename, _ in FILES:
        df = pd.read_csv(BASE / "data" / filename)
        for _, row in df.iterrows():
            stocks = [str(row[f"Stock {i}"]) for i in range(1, 5)]
            sectors = [str(row[f"Sector {i}"]) for i in range(1, 5)]
            assert len(set(stocks)) == 4
            assert len(set(sectors)) == 4

def test_portfolio_ui_has_four_top200_selectors():
    assert 'Top 4-Stock Combos (5Y & 10Y) — tap to open' in APP
    assert 'Top 200 — Best Profit' in APP
    assert 'Top 200 — Best Worst Year' in APP
    assert 'f"combo_{period_label.lower()}_profit_picker"' in APP
    assert 'f"combo_{period_label.lower()}_worst_picker"' in APP

def test_autoload_uses_matching_5y_or_10y_period():
    assert 'args=(picker_key, lookup_key, f"{period_label} Top Profit Generator combo", period_label)' in APP
    assert 'args=(picker_key, lookup_key, f"{period_label} Best Worst-Year combo", period_label)' in APP
    assert 'st.session_state.portfolio_period = period' in APP
