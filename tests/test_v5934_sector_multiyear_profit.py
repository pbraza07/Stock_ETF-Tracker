from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def test_release_version():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.65"


def test_sector_multiyear_profit_selector_remains_compounded():
    assert "def _sector_period_return_series" in APP
    assert "annual_cols = list(YEAR_RETURN_COLS[:years])" in APP
    assert "((1.0 + annual / 100.0).prod(axis=1) - 1.0) * 100.0" in APP
    assert 'drill["_rank"] = _sector_period_return_series(drill, selected_tf)' in APP
    assert 'drill_table["Total Profit %"] = selected_returns' in APP


def test_sector_table_uses_true_calendar_year_returns_not_compounded_horizon_columns():
    assert 'annual_return_cols = list(YEAR_RETURN_COLS)' in APP
    assert 'for year_col in annual_return_cols:' in APP
    assert 'drill_table[year_col] = _sector_numeric_series(drill_table, year_col)' in APP
    assert '*short_return_cols, *annual_return_cols' in APP
    assert '*visible_returns' not in APP[APP.find('drill_cols = list(dict.fromkeys(['):APP.find('drill_cols = list(dict.fromkeys([')+500]


def test_sector_table_forces_explicit_column_order():
    assert 'column_order=drill_cols' in APP
