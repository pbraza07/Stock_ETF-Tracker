from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def test_version_5920():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.20"


def test_buy_signal_alerts_are_collapsible_button():
    assert 'toggle_buy_signal_alerts' in APP
    assert 'buy_signal_alerts_open' in APP
    assert 'Hide Buy Signal Alerts' in APP


def test_portfolio_workspace_uses_build_and_manage_tabs():
    assert 'portfolio_build_tab, portfolio_manage_tab = st.tabs' in APP
    assert '◆ Build Simulation' in APP
    assert '💾 Saved / Manage' in APP
    assert 'toggle_portfolio_simulator' not in APP
    assert 'toggle_portfolio_manager' not in APP


def test_investment_simulator_immediately_precedes_display_mode():
    investment = APP.index("INVESTMENT SIMULATOR")
    display = APP.index("DISPLAY MODE")
    portfolio = APP.index("PORTFOLIO SPLIT SIMULATOR")
    assert portfolio < investment < display
    between = APP[investment:display]
    assert 'PORTFOLIO SPLIT SIMULATOR' not in between


def test_comparison_supports_stocks_and_etfs_unlimited():
    assert 'STOCK & ETF COMPARISON' in APP
    assert 'Stocks & ETFs to compare (unlimited selection)' in APP
    assert 'Select all tracked instruments' in APP
    assert 'Both asset types are supported with no selection limit' in APP
    assert 'all_compare_rows = market.copy()' in APP
    assert 'max_selections' not in APP


def test_etf_cards_have_holdings_and_compare():
    assert 'action_cols = st.columns(4 if is_etf else 3)' in APP
    assert '"Hide Holdings" if holdings_open else "◫ Holdings"' in APP
    assert '"✓ Comparing" if compare_active else "⚖ Compare"' in APP
