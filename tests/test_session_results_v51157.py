from streamlit.testing.v1 import AppTest


def test_ytd_survives_navigation_and_failed_replacement():
    app=AppTest.from_string('''
import pandas as pd
import streamlit as st
from unittest.mock import patch
from runtime_performance import preserve_navigation_state
from ytd_simulator import render_ytd
preserve_navigation_state()
page=st.radio('Page',['YTD','Elsewhere'],key='nav')
st.checkbox('Offline',key='fail')
year=pd.Timestamp.now().year
history=pd.DataFrame({'Close':[100,110,121]},index=pd.to_datetime([f'{year-1}-12-31',f'{year}-01-02',f'{year}-01-05']))
with patch('providers.yahoo.YahooFinanceProvider.download_daily_history_since',side_effect=RuntimeError('offline') if st.session_state.fail else None,return_value={'A':history}), patch('ytd_reports.get_exports'), patch('ytd_reports.render_downloads'):
    if page=='YTD':render_ytd(pd.DataFrame({'Symbol':['A']}))
''').run()
    app.multiselect(key='ytd_holdings').set_value(['A']).run()
    app.number_input(key='ytd_principal').set_value(420000.).run()
    next(b for b in app.button if b.label=='Run YTD simulation').click().run()
    assert not app.exception
    saved=app.session_state.ytd_record
    app.radio(key='nav').set_value('Elsewhere').run()
    app.radio(key='nav').set_value('YTD').run()
    assert app.number_input(key='ytd_principal').value==420000.
    assert app.session_state.ytd_record==saved and len(app.metric)>0
    app.multiselect(key='ytd_holdings').set_value([]).run()
    next(b for b in app.button if b.label=='Run YTD simulation').click().run()
    assert not app.exception and len(app.metric)>0
    assert app.session_state.ytd_record==saved
    app.multiselect(key='ytd_holdings').set_value(['A']).run()
    app.checkbox(key='fail').check().run()
    next(b for b in app.button if b.label=='Run YTD simulation').click().run()
    assert not app.exception and app.session_state.ytd_record==saved and len(app.metric)>0


def test_quality_results_visible_while_pending_and_after_failure():
    from durable_jobs import cancel
    app=AppTest.from_string('''
import streamlit as st
from quality_opportunities_ui import render
from quality_opportunities import screen
from test_quality_opportunities import fixture,monthly_fixture,permissive,YEARS
from runtime_performance import preserve_navigation_state
preserve_navigation_state()
page=st.radio('Page',['Research','Elsewhere'],key='nav')
m,c=fixture();monthly=monthly_fixture(24)
if 'qo_bundle' not in st.session_state:
    st.session_state.qo_bundle=dict(result=screen(m,YEARS,monthly,c,permissive()),market=m,context=c,monthly=monthly,years=YEARS)
if page=='Research':render(m,YEARS,lambda *a:monthly,lambda *a:c)
''').run(timeout=20)
    stamp=app.session_state.qo_bundle['result']['generated_at']
    next(b for b in app.button if b.label=='Evaluate current stock universe').click().run(timeout=20)
    assert not app.exception and len(app.dataframe)>=2
    token=app.session_state.qo_job
    app.radio(key='nav').set_value('Elsewhere').run()
    app.radio(key='nav').set_value('Research').run()
    assert not app.exception and len(app.dataframe)>=2
    cancel(token);app.run(timeout=20)
    assert not app.exception and len(app.dataframe)>=2
    assert app.session_state.qo_bundle['result']['generated_at']==stamp


def test_projection_drafts_preserve_result_reset_clears():
    app=AppTest.from_string('''
import streamlit as st
from future_projection_ui import _apply_payload,_clear_portfolio,_reset_projection
if 'initialized' not in st.session_state:
    st.session_state.initialized=True
    st.session_state.fp_result={'evidence':'original'}
st.button('Import',on_click=_apply_payload,args=({'holdings':['A']},))
st.button('Clear holdings',on_click=_clear_portfolio)
st.button('Reset',on_click=_reset_projection)
''').run()
    app.button[0].click().run()
    assert app.session_state.fp_result=={'evidence':'original'}
    app.button[1].click().run()
    assert app.session_state.fp_result=={'evidence':'original'}
    app.button[2].click().run()
    assert 'fp_result' not in app.session_state


def test_session_isolation_and_portfolio_fallback():
    source='''
import streamlit as st
from session_results import render_retained_portfolio
if st.button('Complete'):
    st.session_state.snapshot={'portfolio_total':1000.,'total_ending':1100.,'total_profit':100.,'total_return':10.,'portfolio_results':[{'symbol':'A','ending_value':1100.}],'selected_portfolio_symbols':['A'],'data_as_of':'2026-01-02'}
if 'snapshot' in st.session_state:render_retained_portfolio(st.session_state.snapshot)
'''
    first=AppTest.from_string(source).run();second=AppTest.from_string(source).run()
    first.button[0].click().run();first.run()
    assert not first.exception and len(first.metric)==4
    assert len(second.metric)==0


def test_sector_portfolio_survives_market_refresh_and_kind_switch(monkeypatch):
    from test_v5116_top12_results import app_for
    from test_v5115_top12 import fixture, YEARS
    from top12_rankings import build_top12_rankings
    import top12_ui as ui
    import pandas as pd
    monkeypatch.setattr(ui,'run_future_projection',lambda *a,**k:{'strategies':{'RB':{
        'summary':{f'P{q} Ending Balance':1000 for q in (10,25,50,75,90)},'table':pd.DataFrame({'Year':[2026]})}}})
    payload={'result':build_top12_rankings(fixture(),YEARS,simulations=100),
             'histories':{'Recession':{},'Max Profit':{}}}
    app=app_for(payload)
    app.button(key='t12_recession').click().run()
    app.button(key='t12_recalculate').click().run()
    app.button(key='t12_build').click().run()
    assert not app.exception
    metrics=[m.value for m in app.metric]
    market=app.session_state.qa_market.copy();market['Price']=999.
    app.session_state.qa_market=market
    app.run()
    assert not app.exception and [m.value for m in app.metric]==metrics
    assert any('Last completed sector portfolio' in c.value for c in app.caption)
    app.button(key='t12_profit').click().run()
    app.button(key='t12_recession').click().run()
    assert not app.exception and [m.value for m in app.metric]==metrics


def test_pending_projection_keeps_completed_result_visible():
    app=AppTest.from_string('''
import streamlit as st
import pandas as pd
from unittest.mock import patch
import future_projection_ui as ui
st.session_state.fp_result={'planning_engine':True,'marker':'Completed evidence'}
st.session_state.fp_job_id='pending'
st.session_state.fp_running=True
with patch('projection_jobs.render_status',side_effect=lambda:st.caption('Working')), patch('planning_ui.render',side_effect=lambda r:st.write(r['marker'])):
    ui.render_future_projection(pd.DataFrame({'Symbol':['A'],'Name':['A'],'Type':['Stock'],'Sector':['Technology']}),['2025'],2025,'2026-01-01','2026-01-01')
''').run(timeout=15)
    assert not app.exception
    assert any('Completed evidence' in m.value for m in app.markdown)
