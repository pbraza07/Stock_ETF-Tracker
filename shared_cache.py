"""Cross-process source cache, single-flight refresh and bounded backoff."""
import time, logging, sqlite3
from concurrent.futures import ThreadPoolExecutor
from performance_store import get,put,key_for,lease,unlock
_pool=ThreadPoolExecutor(max_workers=4,thread_name_prefix='source-refresh')
log=logging.getLogger('marketscope.performance')
_revision=0
_pending=set()
_failures=set()


def _busy(exc):
    return isinstance(exc, sqlite3.OperationalError) and (
        (getattr(exc, 'sqlite_errorcode', 0) & 255) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
        or 'locked' in str(exc).lower() or 'busy' in str(exc).lower())


def _retry_marker(key):
    try:put(key+':retry',True,60)
    except sqlite3.OperationalError as exc:
        if not _busy(exc):raise


def cached(namespace,inputs,loader,ttl=1800,default=None,background=False,valid=None):
    key=key_for(namespace,inputs);row=None;now=time.time()
    try:
        row=get(key)
        if row and row[2]>now:return row[0]
        negative=get(key+':retry')
        if negative and negative[2]>now:return row[0] if row else default
        token=lease(key,600)
    except sqlite3.OperationalError as exc:
        if not _busy(exc):raise
        _failures.add(namespace)
        log.warning('source_cache_busy namespace=%s; retaining saved data',namespace)
        return row[0] if row else default
    if not token:return row[0] if row else default
    def refresh():
        start=time.monotonic()
        try:
            value=loader()
            acceptable=valid(value) if valid else value is not None
            if acceptable:
                put(key,value,ttl);_failures.discard(namespace)
            else:
                _retry_marker(key);_failures.add(namespace)
            return value if acceptable else (row[0] if row else default)
        except Exception as exc:
            _retry_marker(key);_failures.add(namespace)
            log.warning('source_refresh_failed namespace=%s error=%s',namespace,type(exc).__name__)
            return row[0] if row else default
        finally:
            global _revision
            _revision+=1
            _pending.discard(key)
            try:unlock(key,token)
            except sqlite3.OperationalError as exc:
                if not _busy(exc):raise
                log.warning('source_cache_unlock_busy namespace=%s; lease expires automatically',namespace)
            log.info('source_refresh namespace=%s elapsed=%.3f',namespace,time.monotonic()-start)
    if background:
        _pending.add(key)
        _pool.submit(refresh)
        return row[0] if row else default
    return refresh()


def remote(loader,*args,default=None,**kwargs):
    return cached('remote:'+loader.__name__,(args,kwargs),lambda:loader(*args,**kwargs),
        ttl=300,default=default,background=True,
        valid=lambda v:v is not None and (not v.empty if hasattr(v,'empty') else bool(v)))


def render_refresh_status():
    import streamlit as st
    @st.fragment(run_every=3)
    def status():
        previous=st.session_state.get('source_revision',_revision)
        st.session_state['source_revision']=_revision
        if previous!=_revision:st.rerun()
        if _pending:st.caption('Refreshing requested data in the background. Available saved data remains visible.')
        if _failures:st.caption('Some sources could not refresh. Saved data is shown where available; check its observation date before use.')
    status()
