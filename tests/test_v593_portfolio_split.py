from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
CSS = (ROOT / "styles.css").read_text(encoding="utf-8")

def test_portfolio_split_simulator_exists():
    assert "PORTFOLIO SPLIT SIMULATOR" in APP
    assert "portfolio_total_amount" in APP
    assert "portfolio_symbol_picker" in APP
    assert '"Equal split", "Custom %"' in APP
    assert "_portfolio_horizon_projection" in APP
    assert ".portfolio-result-card" in CSS

def test_portfolio_supports_ytd_and_multi_year_horizons():
    assert '["YTD", *[f"{i}Y" for i in range(1, 11)]]' in APP
    assert 'period_choice == "YTD"' in APP
    assert 'value *= factor' in APP

def test_card_period_profit_supports_short_periods_and_years():
    assert 'metric not in PERF_COLS' in APP
    assert 'render_card_profit_period_fragment' in APP
    assert 'st.pills(' in APP
    assert 'card_profit_period_' in APP
