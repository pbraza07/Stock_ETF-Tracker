from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
CSS = (ROOT / "styles.css").read_text(encoding="utf-8")


def test_version_598():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.8"


def test_stock_cards_have_compare_button_and_etfs_keep_holdings():
    assert '"✓ Comparing" if compare_active else "⚖ Compare"' in APP
    assert '"Hide Holdings" if holdings_open else "◫ Holdings"' in APP
    assert 'if is_etf:' in APP


def test_table_view_supports_multirow_compare_selection():
    assert 'selection_mode="multi-row"' in APP
    assert '⚖ Add selected rows to comparison' in APP
    assert 'ETF rows are ignored because this comparison section is stock-only' in APP


def test_unlimited_comparison_has_card_and_table_modes():
    assert 'Stocks to compare (unlimited selection)' in APP
    assert 'Select all tracked stocks' in APP
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
