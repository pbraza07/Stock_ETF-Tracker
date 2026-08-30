from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'app.py').read_text(encoding='utf-8')


def test_release_version():
    assert (ROOT / 'VERSION.txt').read_text(encoding='utf-8').strip() == '5.9.34'


def test_sector_multiyear_profit_is_compounded_from_calendar_years():
    assert 'def _sector_period_return_series' in APP
    assert 'annual_cols = list(YEAR_RETURN_COLS[:years])' in APP
    assert '((1.0 + annual / 100.0).prod(axis=1) - 1.0) * 100.0' in APP
    assert 'drill["_rank"] = _sector_period_return_series(drill, selected_tf)' in APP
    assert 'drill_table["Total Profit %"] = selected_returns' in APP


def test_sector_table_materializes_all_timeframes():
    assert 'for timeframe in visible_returns:' in APP
    assert 'drill_table[timeframe] = _sector_period_return_series(drill_table, timeframe)' in APP
