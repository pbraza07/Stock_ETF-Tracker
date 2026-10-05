import time,threading
from functools import partial
import pytest

@pytest.fixture
def store(tmp_path,monkeypatch):
    monkeypatch.setenv('MARKETSCOPE_STATE_DIR',str(tmp_path))
    monkeypatch.setenv('MARKETSCOPE_EXTERNAL_WORKER','1')
    monkeypatch.delenv('MARKETSCOPE_DATABASE_URL',raising=False)
    return tmp_path

def task(value,progress):progress(1,1,'Done');return value

def test_fifo_retained_result_and_private_id(store):
    from durable_jobs import submit,run_one,poll,cancel
    one=submit(partial(task,42));two=submit(partial(task,99))
    assert poll(one)['state']=='queued' and poll(two)['state']=='queued'
    assert poll('unknown') is None
    assert run_one()
    assert poll(one)['future'].result(timeout=1)==42
    assert poll(two)['state']=='queued'
    cancel(two);assert poll(two)['future'].done()
    assert not run_one()
    with pytest.raises(RuntimeError,match='Cancelled'):poll(two)['future'].result()

def test_running_lease_failure_is_explicit(store):
    from durable_jobs import submit,run_one,poll
    from performance_store import database
    token=submit(partial(task,3))
    with database() as db:db.execute("UPDATE jobs SET state='running',heartbeat=0 WHERE id=?",(token,))
    assert not run_one()
    with pytest.raises(RuntimeError,match='interrupted'):poll(token)['future'].result()

def test_owner_quota_and_global_backpressure(store,monkeypatch):
    from durable_jobs import submit
    submit(partial(task,1),owner='one');submit(partial(task,2),owner='one')
    with pytest.raises(RuntimeError,match='two queued'):submit(partial(task,3),owner='one')
    monkeypatch.setenv('MARKETSCOPE_MAX_QUEUED_JOBS','2')
    with pytest.raises(RuntimeError,match='queue is full'):submit(partial(task,3),owner='two')

def test_stale_while_refresh_does_not_block(store):
    from shared_cache import cached
    from performance_store import put,key_for,get
    key=key_for('test',());put(key,'old',-1)
    ready=threading.Event();finish=threading.Event()
    def loader():ready.set();finish.wait(2);return 'new'
    start=time.monotonic()
    assert cached('test',(),loader,background=True)=='old'
    assert time.monotonic()-start<.5 and ready.wait(1)
    finish.set()
    end=time.monotonic()+2
    while get(key)[0]!='new' and time.monotonic()<end:time.sleep(.01)
    assert get(key)[0]=='new'

def test_security_history_reuse_across_baskets(store):
    import pandas as pd
    from provider_cache import histories_cache
    class Provider:
        calls=[]
        _clean_symbols=staticmethod(lambda s:list(s))
        @histories_cache
        def fetch(self,symbols):
            self.calls.append(symbols)
            return {s:pd.DataFrame({'Close':[1.,2.]}) for s in symbols}
    p=Provider();p.fetch(['A','B']);p.fetch(['B','C']);p.fetch(['C','A'])
    assert p.calls==[['A','B'],['C']]

def test_top_tabs_guarded_and_no_news_snapshot_dependency():
    import ast
    from pathlib import Path
    tree=ast.parse((Path(__file__).parents[1]/'app.py').read_text())
    assert not any(isinstance(n,ast.With) and any(isinstance(i.context_expr,ast.Name) and i.context_expr.id.endswith('_tab') for i in n.items) for n in tree.body)

def test_component_does_not_inline_plotly():
    from pathlib import Path
    source=(Path(__file__).parents[1]/'recession_component/index.html').read_text()
    assert './plotly.min.js' in source and len(source)<5000

def test_on_demand_report_caches_only_requested_format(store,monkeypatch):
    import future_projection
    from report_service import export
    calls=[]
    monkeypatch.setattr(future_projection,'build_pdf_export',lambda r:(calls.append('pdf') or b'%PDF-fixture'))
    monkeypatch.setattr(future_projection,'build_excel_export',lambda r:(_ for _ in ()).throw(AssertionError('Unrequested Excel')))
    assert export({'test':True},'pdf',lambda *a:None)==b'%PDF-fixture'
    assert export({'test':True},'pdf',lambda *a:None)==b'%PDF-fixture'
    assert calls==['pdf']

def test_indexed_archive_preserves_enrichment_and_excludes_undated_from_week(store):
    import news_archive
    from market_news import SOURCES,make_item,utcnow
    from news_repository import query_rows,catalog
    source=next(s for s in SOURCES if s['id']=='bbc')
    dated=make_item('NVIDIA report','NVIDIA earnings rise','https://www.bbc.com/fixture-dated',utcnow().isoformat(),source)
    undated=make_item('NVIDIA undated','NVIDIA report','https://www.bbc.com/fixture-undated',None,source)
    dated['official_text']={'text':'Retained text'}
    news_archive.add([dated,undated],{})
    plain=dict(dated);plain.pop('official_text');news_archive.add([plain],{})
    assert news_archive.load()['articles'][dated['id']]['official_text']['text']=='Retained text'
    total,rows=query_rows(7,symbol='NVDA')
    assert total==1 and rows[0]['id']==dated['id']
    assert query_rows(None,symbol='NVDA')[0]==2
    assert catalog()['stocks']['NVDA']['article_count']==2

def test_input_state_preserves_checkbox_but_not_buttons(store):
    from streamlit.testing.v1 import AppTest
    app=AppTest.from_string('''
import streamlit as st
from runtime_performance import preserve_navigation_state
preserve_navigation_state()
page=st.radio('Page',['A','B'],key='nav')
if page=='A':
    st.checkbox('Option',key='kept_option')
    st.button('Action',key='trigger_action')
''').run()
    app.checkbox[0].check().run()
    app.radio[0].set_value('B').run()
    app.radio[0].set_value('A').run()
    assert not app.exception and app.checkbox[0].value

def test_expired_lease_cannot_release_replacement(store):
    from performance_store import lease,unlock
    first=lease('fixture',-.1)
    second=lease('fixture',60)
    assert first and second and first!=second
    unlock('fixture',first)
    assert lease('fixture',60) is None
    unlock('fixture',second)
    assert lease('fixture',60)

def test_reports_precede_bulk_screens(store):
    from durable_jobs import submit,run_one,poll
    screen=submit(partial(task,'screen'),priority=20)
    report=submit(partial(task,'report'),priority=0)
    assert run_one()
    assert poll(report)['future'].result(timeout=1)=='report'
    assert poll(screen)['state']=='queued'
