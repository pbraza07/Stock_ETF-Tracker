from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
CSS = (ROOT / "styles.css").read_text(encoding="utf-8")


def test_version_598():
    assert tuple(map(int, (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip().split("."))) >= (5, 9, 8)


def test_stock_cards_direct_comparison_choice_to_single_selector_and_etfs_keep_holdings():
    assert 'Compare from the Stock & ETF Comparison tab' in APP
    assert 'key=f"compare_{symbol}_{page_start}"' not in APP
    assert '"Hide Holdings" if holdings_open else "◫ Holdings"' in APP
    assert 'if is_etf:' in APP


def test_table_view_no_longer_changes_comparison_membership():
    assert 'selection_mode="multi-row"' in APP
    assert '⚖ Add selected rows to comparison' not in APP
    assert 'use the single searchable selector in the Stock & ETF Comparison tab' in APP


def test_unlimited_comparison_has_card_and_table_modes():
    assert 'Stocks & ETFs to compare (unlimited selection)' in APP
    assert 'key="stock_compare_selector"' in APP
    assert 'Comparison Cards' in APP
    assert 'Comparison Table' in APP
    assert 'COMPARE_CARDS_PER_PAGE = 12' in APP
    assert 'max_selections' not in APP


def test_comparison_table_includes_performance_and_simulation_fields():
    assert '*PERF_COLS' in APP
    assert '"Profit / Loss ($)"' in APP
    assert '"Simulation Return %"' in APP
    assert 'Sort comparison by' in APP


def test_comparison_css_present():
    assert '.comparison-workspace-header' in CSS
    assert '.comparison-instrument-card' in CSS
