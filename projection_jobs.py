"""Durable calculation queue and Streamlit status adapter."""
from durable_jobs import submit as _submit,poll,release,cancel

def submit(task,priority=10):
    import streamlit as st
    from uuid import uuid4
    owner=st.session_state.setdefault('calculation_owner',uuid4().hex)
    return _submit(task,owner=owner,priority=priority)

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
        st.caption('Private recovery ID: '+token)
        if st.button('Cancel calculation',key='fp_cancel_job'):
            cancel(token)
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
        st.caption('Calculation continues in the worker during ordinary page reruns or a brief reconnect. Keep this browser session. Queued jobs and completed results are retained in durable storage. An interrupted running job reports a failure instead of silently restarting.')
    status()
