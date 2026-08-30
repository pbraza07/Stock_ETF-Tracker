from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'app.py').read_text(encoding='utf-8')
YEARS = [str(y) for y in range(2025, 2015, -1)]


def _rows(name):
    with (ROOT / 'data' / name).open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def test_rank_files_have_50_rows_and_required_semiconductor_quota():
    for filename in ['top50_profit_generators_10y.csv', 'top50_best_worst_year_10y.csv']:
        rows = _rows(filename)
        assert len(rows) == 50
        assert sum(r['Includes Semiconductor'] == 'Yes' for r in rows) == 10
        assert sum(r['Includes Semiconductor'] == 'No' for r in rows) == 40
        for r in rows:
            sectors = [r[f'Sector {i}'] for i in range(1, 5)]
            assert len(set(sectors)) == 4
            for year in YEARS:
                assert year in r and r[year] != ''
            assert r['Total Profit ($)'] != ''
            assert r['Worst Year %'] != ''


def test_portfolio_ui_has_two_rank_dropdowns_tables_and_autoload():
    assert 'Top 4-Stock Combos (10Y) — tap to open' in APP
    assert 'Top 50 — Best Profit Generator' in APP
    assert 'Top 50 — Best Worst Year' in APP
    assert 'combo_profit_picker' in APP
    assert 'combo_worst_picker' in APP
    assert '_apply_ranked_combo_selection' in APP
    assert 'st.session_state.portfolio_symbol_picker = symbols' in APP
    assert 'st.session_state.portfolio_period = "10Y"' in APP
    assert 'st.session_state.portfolio_allocation_mode = "Equal split"' in APP
    assert 'Profit Top 50 table' in APP
    assert 'Best Worst-Year Top 50 table' in APP


def test_rank_source_is_packaged():
    source = ROOT / 'data' / 'portfolio_combo_source_2026-08-29.csv'
    assert source.exists() and source.stat().st_size > 1000
