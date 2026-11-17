import threading
import time
import pandas as pd
import workspace_loading as loading


def test_provider_wait_does_not_block_navigation_and_duplicate_calls_share_work():
    started, finish = threading.Event(), threading.Event()
    calls = []
    old = {'data': [{'date': '2026-01-01', 'value': 5}], 'status': 'Saved snapshot'}
    def loader():
        calls.append(1); started.set(); finish.wait(3)
        return {'data': [{'date': '2026-02-01', 'value': 6}], 'status': 'Updated'}
    key = ('test', time.monotonic())
    start = time.monotonic()
    value, pending = loading.request(key, loader, lambda: old)
    assert time.monotonic() - start < .2
    assert value == old and pending and started.wait(1)
    for _ in range(5):
        assert loading.request(key, loader, lambda: old, force=True)[0] == old
    assert len(calls) == 1
    finish.set(); loading._entries[key]['future'].result(2)
    value, pending = loading.request(key, loader, lambda: old)
    assert not pending and value['data'][0]['value'] == 6
    value['data'][0]['value'] = 99
    assert loading.request(key, loader, lambda: old)[0]['data'][0]['value'] == 6


def test_failure_retains_data_and_backoff_prevents_navigation_retry_storm():
    key = ('failure', time.monotonic()); calls = []
    def fail():
        calls.append(1)
        return {'data': [], 'status': 'Unavailable', 'error': 'HTTP 429'}
    old = {'data': [1], 'retrieved_at': 'original', 'status': 'Saved snapshot'}
    loading.request(key, fail, lambda: old)
    loading._entries[key]['future'].result(2)
    value, pending = loading.request(key, fail, lambda: old)
    assert value['data'] == [1] and value['retrieved_at'] == 'original'
    assert value['status'] == 'Stale cache' and not pending
    assert len(calls) == 1


def test_exact_market_inputs_reuse_and_mutations_invalidate():
    state = {}; calls = []
    snapshot = pd.DataFrame({'Symbol': ['A'], 'Price': [100.]})
    def build():
        calls.append(1); return snapshot.copy()
    result = loading.reuse_market(state, (snapshot, {}), build)
    result.loc[0, 'Price'] = 999
    pd.testing.assert_frame_equal(loading.reuse_market(state, (snapshot, {}), build), snapshot)
    assert len(calls) == 1
    snapshot.loc[0, 'Price'] = 101
    assert loading.reuse_market(state, (snapshot, {}), build).loc[0, 'Price'] == 101
    assert len(calls) == 2
    loading.reuse_market(state, (snapshot, {'A': {'Price': 102}}), build)
    assert len(calls) == 3


def test_background_completion_does_not_force_full_page_rerun():
    from pathlib import Path
    source = Path('shared_cache.py').read_text()
    assert 'if previous!=_revision:st.rerun()' not in source
    assert "key='apply_source_updates'" in source
    assert 'run_every=' not in source


def test_recession_page_renders_saved_observations_without_waiting(monkeypatch):
    from streamlit.testing.v1 import AppTest
    import free_data_evidence
    monkeypatch.setattr(free_data_evidence, 'render_free_evidence', lambda *a: None)
    monkeypatch.setattr(loading, 'request', lambda *a, **k: ({
        'data': [{'date': '2025-01-01', 'value': .2}, {'date': '2025-02-01', 'value': .3}],
        'status': 'Saved snapshot', 'retrieved_at': '2025-03-01T00:00:00+00:00', 'error': None}, True))
    app = AppTest.from_string('from recession_indicators import render_recession_indicators\nrender_recession_indicators()').run()
    assert not app.exception
    assert len(app.metric) == 12
    assert any(b.label == 'Check completed recession downloads' for b in app.button)
    app.selectbox(key='recession_history_window').set_value('5 years').run()
    assert not app.exception and len(app.metric) == 12
