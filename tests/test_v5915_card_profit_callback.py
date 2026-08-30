from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
CSS = (ROOT / "styles.css").read_text(encoding="utf-8")


def test_profit_tiles_use_pre_rerun_callback_state():
    assert "def _set_card_profit_period" in APP
    assert "on_click=_set_card_profit_period" in APP
    assert "args=(symbol, metric, clean_namespace)" in APP
    assert 'st.session_state[f"card_profit_period_selected_{clean_namespace}_{clean_symbol}"] = metric' in APP


def test_profit_math_uses_selected_metric_and_principal():
    assert 'pct = pd.to_numeric(pd.Series([row.get(metric)])' in APP
    assert 'ending_value = principal * (1.0 + float(pct) / 100.0)' in APP
    assert '"profit": ending_value - principal' in APP


def test_period_controls_and_result_are_inside_keyed_card_shell():
    card_open = APP.index('with st.container(border=True, key=f"market_card_{safe_card_symbol}")')
    selector = APP.index('render_card_profit_period_fragment(row.to_dict(), float(investment_amount), namespace="navigator")', card_open)
    result = APP.index('st.markdown(_investment_html(row)', selector)
    assert card_open < selector < result
    assert 'div[class*="st-key-market_card_"]' in CSS
    assert 'min-height: 735px' in CSS
