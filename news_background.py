"""Non-blocking shared collector; no Streamlit objects in background tasks."""
from concurrent.futures import ThreadPoolExecutor
from performance_store import lease,unlock,put,get
_pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='news-collector')

def collect_now(token):
    import news_archive
    from market_news import collect
    try:
        news_archive.restore()
        rows,status=collect()
        payload=news_archive.add(rows,status)
        news_archive.sync()
        put('news:last-status','Collection completed',900)
        return payload
    except Exception as exc:
        put('news:last-status','Refresh failed ('+type(exc).__name__+'); saved articles retained.',60)
    finally:unlock('news:refresh',token)

def request():
    token=lease('news:refresh',300)
    if token:
        _pool.submit(collect_now,token)
        return 'Refreshing feeds in the background. Saved news remains available.'
    return 'A news refresh is already in progress.'
