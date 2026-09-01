from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def test_sort_options_are_collapsible_behind_button():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert '"sort_menu_open"' in app
    assert '"✦ Sort Cards By"' in app
    assert 'if st.session_state.sort_menu_open:' in app
    assert 'SORT_OPTIONS = ["Market Cap", "Total Profit ($)", *PERF_COLS, "Rating"]' in app


def test_etf_cards_use_sector_as_display_name():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'def _card_display_name' in app
    assert 'if instrument_type == "ETF":' in app
    assert 'sector = str(row.get("Sector") or "").strip()' in app
    assert 'name = _card_display_name(row)' in app


def test_open_instrument_loads_chart_and_scrolls_once():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'st.session_state.scroll_to_chart = True' in app
    assert 'cached_max_chart_history(selected)' in app
    assert 'instrument-chart-anchor' in app
    assert 'scrollIntoView' in app
    assert 'st.session_state.scroll_to_chart = False' in app


def test_mobile_year_order_is_explicit_and_responsive():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    css = (ROOT / "styles.css").read_text(encoding="utf-8")
    assert 'chart_year_options = [str(current_year - offset) for offset in range(0, 26)]' in app
    assert 'def _detail_performance_html' in app
    assert 'detail-performance-grid' in css
    assert 'grid-template-columns: repeat(2' in css
    assert '[data-testid="stSegmentedControl"] [role="radiogroup"]' in css


def test_213_etf_sources_remain_exact():
    data = ROOT / "data"
    allow = pd.read_csv(data / "etf_allowlist.csv")
    generated = pd.read_csv(data / "default_universe.csv")
    bootstrap = pd.read_csv(data / "default_universe.bootstrap.csv")
    assert len(allow) == 213
    assert int((generated["Type"].astype(str).str.upper() == "ETF").sum()) == 213
    assert int((bootstrap["Type"].astype(str).str.upper() == "ETF").sum()) == 213
