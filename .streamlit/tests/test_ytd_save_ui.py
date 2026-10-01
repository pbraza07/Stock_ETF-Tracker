from streamlit.testing.v1 import AppTest


def test_run_save_and_reopen_snapshot():
    app = AppTest.from_string('''
import pandas as pd
import streamlit as st
from unittest.mock import patch
from ytd_simulator import render_ytd, render_saved_ytd
year = pd.Timestamp.now().year
history = pd.DataFrame({'Close':[100,110,121]}, index=pd.to_datetime([f'{year-1}-12-31',f'{year}-01-02',f'{year}-01-05']))
def save(records, *args):
    st.session_state.saved_test = records[-1]
    return True, 'Saved snapshot'
with patch('providers.yahoo.YahooFinanceProvider.download_daily_history_since', return_value={'A':history}), patch('portfolio_simulations.load_saved_simulations', return_value=[]), patch('portfolio_simulations.persist_saved_simulations', side_effect=save), patch('pdf_storage.persist_pdf_artifact',return_value=(True,'PDF saved',{})), patch('pdf_storage.load_pdf_artifact',return_value=b'%PDF'):
    render_ytd(pd.DataFrame({'Symbol':['A']}))
    if 'saved_test' in st.session_state:
        render_saved_ytd(st.session_state.saved_test)
''').run()
    app.multiselect[0].set_value(['A']).run()
    app.button[0].click().run()
    assert not app.exception
    assert len(app.dataframe) == 2
    assert len(app.metric) == 8
    assert app.get('progress')[0].value == 100
    assert any('Download YTD Excel' == b.label for b in app.get('download_button'))
    app.number_input[0].set_value(400000).run()
    app.button(key='save_ytd_simulation').click().run()
    assert not app.exception
    record = app.session_state.saved_test
    assert record['inputs']['principal'] == 300000
    assert record['strategies']['Rebalanced']['snapshot']['Beginning Balance'] == 300000
    assert len(app.dataframe) == 4
