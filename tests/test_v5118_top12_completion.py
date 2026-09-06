"""Regression for stalled history and table publication without an app rerun."""
from concurrent.futures import Future
from threading import Event
from time import monotonic
from unittest.mock import patch
import pytest
from streamlit.testing.v1 import AppTest
from test_v5115_top12 import fixture, YEARS
from test_v5116_top12_results import payload, Executor
import top12_jobs as jobs


def test_stalled_remote_history_has_shared_deadline_and_keeps_local_incumbents(payload):
    release = Event()
    local = {kind: {'runs': [{'Holdings': payload['result'][kind].to_dict('records')}]}
             for kind in ('Recession', 'Max Profit')}
    def stalled(kind, remote=True):
        if remote:
            release.wait(3)
        return local[kind]
    try:
        with patch.object(jobs, 'HISTORY_WAIT_SECONDS', 0.02), patch.object(jobs, 'load_ledger', stalled), patch.object(jobs, 'record_run', side_effect=lambda h,*a: h), patch.object(jobs, 'build_top12_rankings', return_value=payload['result']) as build:
            started = monotonic()
            output = jobs.calculate_rankings(fixture(), YEARS, 'asof', lambda *a:{}, lambda *a:{}, 1.0, {})
            assert monotonic()-started < 1.0
        assert len(output['result']['Recession']) == 12
        assert len(output['result']['Max Profit']) == 12
        assert len(build.call_args.kwargs['previous']['Recession']) == 12
    finally:
        release.set()


@pytest.mark.parametrize('kind', ['Recession', 'Max Profit'])
def test_poll_publishes_table_without_full_app_rerun(payload, kind):
    source = '''
import streamlit as st
import top12_ui as ui
from unittest.mock import patch
with patch.object(ui, 'SAVE_EXECUTOR', st.session_state.executor), patch.object(ui, 'ranking_exports', return_value=(b'excel', b'pdf')), patch.object(st, 'rerun', side_effect=AssertionError('Full app rerun must not be required')):
    ui.watch_ranking_jobs(st.session_state.market, st.session_state.years, 'asof', lambda *a:{}, lambda *a:{}, 'fingerprint')
'''
    app = AppTest.from_string(source)
    future = Future()
    app.session_state.executor = Executor(payload)
    app.session_state.market = fixture()
    app.session_state.years = YEARS
    app.session_state.t12_input_view = kind
    app.session_state.t12_job = {'future': future, 'fingerprint':'fingerprint', 'progress':{'stage':'Loading saved selections and monthly evidence'}}
    app.run()
    assert not app.dataframe
    future.set_result(payload)
    app.run()
    assert not app.exception
    assert len(app.dataframe[0].value) == 12
    assert kind + ' Score' in app.dataframe[0].value
    app.run()
    assert not app.exception and len(app.dataframe[0].value) == 12


def test_persistence_cannot_occupy_calculation_executor():
    assert jobs.SAVE_EXECUTOR is not jobs.EXECUTOR
