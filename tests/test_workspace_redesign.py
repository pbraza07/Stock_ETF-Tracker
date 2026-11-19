from streamlit.testing.v1 import AppTest

def test_navigation_preserves_results_and_opens_only_selected_workspace():
    app=AppTest.from_string('''
import streamlit as st
from workspace_navigation import render_navigation
from workspace_navigation import DESTINATIONS
labels=list(DESTINATIONS)
st.session_state.setdefault('saved_result', 12345)
for label, page in zip(labels,render_navigation(labels)):
    if page.open:
        with page: st.text('Active: '+label)
st.text(str(st.session_state.saved_result))
''').run()
    assert not app.exception
    assert [t.value for t in app.text]==['Active: 📰 Market News','12345']
    app.segmented_control[0].set_value('Plan').run()
    app.selectbox[0].select('Future Projection').run()
    assert [t.value for t in app.text]==['Active: Future Projection','12345']
    app.segmented_control[0].set_value('Markets').run()
    assert [t.value for t in app.text]==['Active: 📰 Market News','12345']

def test_news_bootstrap_deduplicates(monkeypatch):
    import news_background as n
    from concurrent.futures import Future
    class Pool:
        calls=0
        def submit(self,fn):
            self.calls+=1
            return Future()
    pool=Pool()
    monkeypatch.setattr(n,'_pool',pool)
    monkeypatch.setattr(n,'_bootstrap_future',None)
    assert n.prepare_archive() is n.prepare_archive()
    assert pool.calls==1
