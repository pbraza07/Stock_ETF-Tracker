import threading
import numpy as np
import pandas as pd
import pytest
from planning_paths import generate_paths
from planning_cashflows import simulate
from planning_assumptions import settings,forward_cma
from future_projection import prepare_projection_model,normalize_projection_inputs
from test_v510_future_projection import market_fixture,base_inputs,YEARS

def test_disk_paths_identical_to_memory(tmp_path):
    inputs=normalize_projection_inputs(base_inputs())
    model=prepare_projection_model(market_fixture(),inputs['holdings'],YEARS,use_monthly=True)
    cfg=settings({'cma_inputs':{'treasury_yield':.04}});cma=forward_cma({},cfg)
    a=generate_paths(model,{},cma,cfg,2,80,123)
    b=generate_paths(model,{},cma,cfg,2,80,123,workdir=tmp_path)
    assert isinstance(b['returns'],np.memmap)
    assert np.array_equal(a['returns'],b['returns'])
    assert np.array_equal(a['inflation'],b['inflation'])

def test_balance_capture_not_required_for_identical_statistics():
    inputs=normalize_projection_inputs(base_inputs())
    returns=np.random.default_rng(3).normal(0,.02,(24,20,4))
    a=simulate(returns,inputs,settings(),'Rebalanced')
    b=simulate(returns,inputs,settings(),'Rebalanced',capture_balances=True)
    assert a['balances'].size==0 and b['balances'].shape==(24,20)
    pd.testing.assert_frame_equal(a['table'],b['table'])
    assert a['summary']==b['summary']

def test_job_survives_polling_and_rejects_concurrent_submission():
    from projection_jobs import submit,poll,release
    ready=threading.Event();finish=threading.Event()
    def task(progress):
        progress(3,12,'Forecast months');ready.set();finish.wait(5);return {'done':True}
    token=submit(task)
    try:
        assert ready.wait(2)
        assert poll(token)['progress']==(3,12,'Forecast months')
        with pytest.raises(RuntimeError,match='Another projection'):submit(task)
        assert poll('not-an-owned-job') is None
        finish.set()
        assert poll(token)['future'].result(timeout=5)=={'done':True}
    finally:finish.set();poll(token)['future'].result(timeout=5);release(token)
    assert poll(token) is None

def test_failed_job_releases_capacity():
    from projection_jobs import submit,poll,release
    def fail(progress):raise ValueError('fixture failure')
    token=submit(fail)
    with pytest.raises(ValueError):poll(token)['future'].result(timeout=5)
    release(token)
    second=submit(lambda cb:42)
    assert poll(second)['future'].result(timeout=5)==42
    release(second)

def test_completed_job_handoff_renders_result_and_caches():
    from streamlit.testing.v1 import AppTest
    app=AppTest.from_string('''
import streamlit as st
from projection_jobs import submit,poll,render_status
if not st.session_state.get('started'):
    st.session_state.started=True
    st.session_state.fp_job_id=submit(lambda cb: {'verified':42})
    poll(st.session_state.fp_job_id)['future'].result(timeout=5)
    st.session_state.fp_job_cache_key='fixture-key'
    st.session_state.fp_running=True
if st.session_state.get('fp_job_id'):render_status()
else:st.success(str(st.session_state.fp_result['verified']))
''').run(timeout=10)
    assert not app.exception
    assert app.success[0].value=='42'
    assert not app.session_state.fp_running
    assert app.session_state.fp_result_cache['fixture-key']=={'verified':42}

def test_missing_job_unlocks_controls_after_rerun():
    from streamlit.testing.v1 import AppTest
    app=AppTest.from_string('''
import streamlit as st
from projection_jobs import render_status
if not st.session_state.get('started'):
    st.session_state.started=True
    st.session_state.fp_job_id='expired-worker'
    st.session_state.fp_running=True
if st.session_state.get('fp_job_id'):render_status()
else:st.button('Run Projection',disabled=st.session_state.fp_running)
''').run(timeout=10)
    assert not app.exception
    assert not app.button[0].disabled
    assert 'no longer available' in app.session_state.fp_job_error
