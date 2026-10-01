"""Process-owned jobs: survive UI reruns; serialize heavy projection workloads.

Jobs are accessible only through opaque IDs retained by their owning session.
No query-string tokens or cross-session input-based result lookup.
Process restarts and new browser sessions do not preserve these jobs.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from time import monotonic
from uuid import uuid4
import logging

_log=logging.getLogger('marketscope.projection')
_log.setLevel(logging.INFO)
if not _log.handlers:
    _handler=logging.StreamHandler()
    _handler.setFormatter(logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s'))
    _log.addHandler(_handler)
_log.propagate=False

_pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='projection-job')
_lock=Lock();_jobs={}
TTL=1800

def submit(task):
    with _lock:
        for key in list(_jobs):
            job=_jobs[key]
            if job['future'].done() and monotonic()-job['created']>TTL:del _jobs[key]
        if any(not job['future'].done() for job in _jobs.values()):
            raise RuntimeError('Another projection is running on this server. Wait for it to finish before starting a new one.')
        token=uuid4().hex
        job={'progress':(0,1,'Preparing projection'),'created':monotonic()}
        def progress(completed,total,label):
            with _lock:job['progress']=(completed,total,label)
        def run():
            _log.info('Projection started job=%s',token[:8])
            try:
                result=task(progress)
                _log.info('Projection completed job=%s elapsed_seconds=%.1f',token[:8],monotonic()-job['created'])
                return result
            except Exception as exc:
                # No holdings, balances, API keys or full recovery token in logs.
                _log.error('Projection failed job=%s error_type=%s elapsed_seconds=%.1f',token[:8],type(exc).__name__,monotonic()-job['created'])
                raise
        job['future']=_pool.submit(run)
        _jobs[token]=job
        return token

def poll(token):
    with _lock:
        job=_jobs.get(token)
        if job is None:return None
        return {'progress':job['progress'],'future':job['future']}

def release(token):
    with _lock:
        job=_jobs.get(token)
        if job is not None and job['future'].done():del _jobs[token]

def render_status():
    import streamlit as st
    @st.fragment(run_every=3)
    def status():
        token=st.session_state.get('fp_job_id');job=poll(token)
        if job is None:
            st.session_state.fp_running=False
            st.session_state.pop('fp_job_id',None)
            st.session_state.pop('fp_job_cache_key',None)
            st.session_state.fp_job_error='The projection worker is no longer available, possibly after a server restart. Run Projection to retry.'
            st.rerun()
        future=job['future']
        if future.done():
            try:
                st.session_state.fp_result=future.result()
                key=st.session_state.pop('fp_job_cache_key',None)
                if key:
                    cache=dict(st.session_state.get('fp_result_cache') or {})
                    cache[key]=st.session_state.fp_result
                    while len(cache)>2:cache.pop(next(iter(cache)))
                    st.session_state.fp_result_cache=cache
            except Exception as exc:st.session_state['fp_job_error']=str(exc)
            finally:
                st.session_state.pop('fp_job_cache_key',None)
                release(token);st.session_state.fp_running=False;st.session_state.pop('fp_job_id',None)
            st.rerun()
        completed,total,label=job['progress']
        percent=min(.99,completed/max(1,total))
        st.progress(percent,text=f'{label}: {completed:,} / {total:,} ({percent:.0%} of this stage)')
        st.caption('Calculation continues on this server during ordinary page reruns or a brief reconnect. Keep this browser session. A server restart requires rerunning; no automatic repeated submission occurs.')
    status()
