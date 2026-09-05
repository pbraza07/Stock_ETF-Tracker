from pathlib import Path

APP = Path("app.py").read_text(encoding="utf-8")

def test_sidebar_market_controls_removed():
    assert "with st.sidebar:" not in APP
    assert 'st.subheader("Market controls")' not in APP
    assert 'st.subheader("Find any stock or ETF")' not in APP

def test_card_fragment_and_rendering_are_in_card_tab_scope():
    lines = APP.splitlines()
    default_line = next(line for line in lines if "def _default_profit_metric" in line)
    frag_line = next(line for line in lines if "def render_card_profit_period_fragment" in line)
    anchor_line = next(line for line in lines if "def _card_anchor_id" in line)
    rows_line = next(line for line in lines if "rows = list(card_rows.iterrows())" in line)
    assert default_line.startswith("        def ")
    assert frag_line.startswith("        def ")
    assert anchor_line.startswith("        def ")
    assert rows_line.startswith("        rows = ")

def test_both_view_searches_retained():
    assert 'key="card_local_search_selector"' in APP
    assert 'key="table_local_search_selector"' in APP

def test_all_instrument_fallback():
    assert 'instrument_filter = instrument_filter or "All"' in APP
