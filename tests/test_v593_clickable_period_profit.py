from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
CSS = (ROOT / "styles.css").read_text(encoding="utf-8")


def test_return_periods_have_card_local_profit_controls():
    assert 'def _period_profit_projection' in APP
    assert 'def render_card_profit_period_fragment' in APP
    assert '@st.fragment' in APP
    assert 'st.pills(' in APP
    assert 'card_profit_period_' in APP
    assert 'SELECTED PERIOD' in APP
    assert '.period-profit-card' in CSS


def test_period_profit_does_not_use_query_navigation_or_scroll_jump():
    assert 'def _period_profit_href' not in APP
    assert 'profit_scroll_token' not in APP
    assert 'SELECTED_PROFIT_PERIOD' not in APP
    assert 'urlencode' not in APP
    assert 'updates only this card area' in APP


def test_ytd_is_a_first_class_investment_period():
    assert '["YTD", *[f"{i}Y" for i in range(1, 21)]]' in APP
    assert 'investment_is_ytd = investment_period_choice == "YTD"' in APP
    assert 'if int(years_requested) == 0:' in APP
    assert 'YTD-only calculation' in APP
