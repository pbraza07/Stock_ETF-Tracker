from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
CSS = (ROOT / "styles.css").read_text(encoding="utf-8")


def test_top_level_workspace_tabs_exist():
    assert 'market_tab, portfolio_tab, compare_tab, alerts_tab = st.tabs' in APP
    for label in ["Market Navigator", "Portfolio Simulator", "Stock & ETF Comparison", "Alerts & Help"]:
        assert label in APP


def test_market_navigator_groups_requested_controls():
    market_start = APP.index("with market_tab:")
    portfolio_start = APP.index("with portfolio_tab:")
    first_market = APP[market_start:portfolio_start]
    assert "Quick filters" in first_market
    second_market = APP[APP.index("with market_tab:", portfolio_start):APP.index("with compare_tab:")]
    assert "INVESTMENT SIMULATOR" in second_market
    assert "DISPLAY MODE" in second_market
    assert "MARKET NAVIGATOR" in second_market


def test_compact_github_setup_popover_hides_secret_value():
    assert 'st.popover("ⓘ PDF Setup"' in APP
    assert 'os.getenv("MARKETSCOPE_GITHUB_TOKEN")' in APP
    assert "MarketScope only checks whether the secret exists" in APP


def test_comparison_search_is_enhanced_and_can_discover_external_instruments():
    for field in ["Symbol", "Name", "Type", "Sector", "Industry", "Analyst Rating"]:
        assert f'"{field}"' in APP
    assert 'key="comparison_enhanced_search"' in APP
    assert 'provider.search(str(comparison_search_query).strip(), max_results=12)' in APP
    assert 'Track + compare' in APP
    assert 'persist_snapshot(durable, SNAPSHOT_FILE' in APP


def test_mobile_tab_bar_can_scroll_horizontally():
    assert 'overflow-x: auto' in CSS
    assert 'white-space: nowrap' in CSS
