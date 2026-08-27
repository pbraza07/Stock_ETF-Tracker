from pathlib import Path
import numpy as np
import pandas as pd
from analytics import calculate_performance

ROOT = Path(__file__).resolve().parents[1]

def _history():
    idx = pd.bdate_range('2014-01-02', periods=3200)
    x = np.arange(len(idx), dtype=float)
    return pd.DataFrame({'Close': 80 + 0.08*x + 2*np.sin(x/17)}, index=idx)

def test_all_annualized_horizons_1_to_10_exist():
    p = calculate_performance(_history())
    for y in range(1, 11):
        assert getattr(p, f'avg_{y}y') is not None

def test_requested_performance_order_is_exact():
    app = (ROOT/'app.py').read_text(encoding='utf-8')
    wanted = '["1D", "1M", "3M", "6M", "YTD", "1Y Avg", "2Y Avg", "3Y Avg", "4Y Avg", "5Y Avg", "6Y Avg", "7Y Avg", "8Y Avg", "9Y Avg", "10Y Avg"]'
    assert f'PERF_COLS = {wanted}' in app

def test_cards_replace_main_dataframe_table():
    app = (ROOT/'app.py').read_text(encoding='utf-8')
    assert 'Futuristic card navigator' in app
    assert 'instrument-card' in app
    assert 'Open {symbol}' in app
    assert '# Main sortable table' not in app
    # Alert mini-table may remain; the primary market navigator must not use dataframe.
    nav = app[app.index('# Futuristic card navigator'):app.index('with st.expander("Data methodology')]
    assert 'st.dataframe(' not in nav

def test_futuristic_css_and_mobile_card_styles_exist():
    css = (ROOT/'styles.css').read_text(encoding='utf-8')
    for token in ['.instrument-card', '.navigator-title', '.detail-header', '@media (max-width: 900px)']:
        assert token in css
