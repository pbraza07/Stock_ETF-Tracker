from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def test_v5935_version():
    assert (ROOT / "VERSION.txt").read_text().strip() == "5.11.8"


def test_profit_timeframe_options_are_strict_numeric_1_to_25():
    assert 'timeframe_options = ["1D", "1M", "3M", "6M", "YTD", *ANNUAL_HORIZON_OPTIONS]' in APP


def test_table_displays_calendar_year_returns_as_individual_annual_returns():
    assert 'annual_return_cols = list(YEAR_RETURN_COLS)' in APP
    assert 'drill_table[year_col] = _sector_numeric_series(drill_table, year_col)' in APP
    assert 'column_order=drill_cols' in APP


def test_total_profit_still_uses_selected_timeframe_engine():
    assert 'selected_returns = _sector_period_return_series(drill_table, selected_tf)' in APP
    assert 'float(profit_basis) * selected_returns / 100.0' in APP
