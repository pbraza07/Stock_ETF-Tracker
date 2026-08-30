from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")

def test_release_version():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.38"

def test_selector_commits_state_with_callback():
    assert "def _commit_stock_compare_selector()" in APP
    assert "on_change=_commit_stock_compare_selector" in APP
    assert "st.session_state.compare_symbols = selected" in APP

def test_fresh_widget_choice_is_not_overwritten_by_old_compare_state():
    forbidden = "if list(st.session_state.stock_compare_selector) != valid_compare_symbols:"
    assert forbidden not in APP
    assert "Never write the old compare state back into the widget" in APP

def test_selected_state_drives_cards_table_and_logos():
    assert "comparison_symbols = [s for s in st.session_state.compare_symbols if s in valid_symbol_set]" in APP
    assert "comparison_logo_urls = cached_logo_urls(tuple(comparison_symbols))" in APP
    assert 'st.tabs(["▦ Comparison Cards", "▤ Comparison Table"])' in APP
