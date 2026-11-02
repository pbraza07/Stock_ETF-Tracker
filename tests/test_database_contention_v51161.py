import json,sqlite3,time,threading
from concurrent.futures import ThreadPoolExecutor
import pytest
from performance_store import database,put,get,lease,unlock,key_for,state_dir
from shared_cache import cached
from test_market_news import item


def payload(row):
    return dict(schema=1,articles={row['id']:row},sources={},updated_at=row['last_seen_at'])


def test_actual_shared_writer_lock_keeps_expired_valid_evidence():
    key=key_for('lock-fixture',())
    put(key,{'as_of':'2026-11-01','price':123.},-1)
    blocker=sqlite3.connect(state_dir()/'performance.sqlite',isolation_level=None)
    blocker.execute('BEGIN IMMEDIATE')
    try:
        start=time.monotonic()
        result=cached('lock-fixture',(),lambda:pytest.fail('Must not fetch without a lease'),background=True)
        assert result=={'as_of':'2026-11-01','price':123.}
        assert time.monotonic()-start<3
    finally:blocker.execute('ROLLBACK');blocker.close()
    assert cached('lock-fixture',(),lambda:{'as_of':'2026-11-02','price':125.})['price']==125.


def test_news_writer_lock_does_not_block_cache_or_jobs():
    import news_repository as repo
    repo.init()
    with repo.database() as news:
        news.execute('BEGIN IMMEDIATE')
        try:
            start=time.monotonic()
            token=lease('independent',5);assert token
            from durable_jobs import submit,poll
            job=submit(lambda progress:123)
            assert poll(job)['state']=='queued'
            put('quote',{'price':123.})
            assert get('quote')[0]['price']==123.
            assert time.monotonic()-start<1
            unlock('independent',token)
        finally:news.execute('ROLLBACK')


def test_slow_analysis_holds_no_write_transaction(monkeypatch):
    import news_repository as repo,news_context
    row=item(slug='slow-lock-fixture');repo.init()
    entered=threading.Event();finish=threading.Event()
    original=news_context.story_context
    def slow(row):
        entered.set();assert finish.wait(5)
        return original(row)
    monkeypatch.setattr(news_context,'story_context',slow)
    with ThreadPoolExecutor(max_workers=1) as pool:
        task=pool.submit(repo.save,payload(row))
        try:
            assert entered.wait(3)
            with repo.database() as db:
                db.execute('BEGIN IMMEDIATE');db.execute('COMMIT')
        finally:finish.set()
        task.result(timeout=5)
    assert repo.load()['articles'][row['id']]['title']==row['title']


def test_concurrent_article_updates_preserve_enrichment(monkeypatch):
    import news_repository as repo,news_context
    row=item(slug='overlap-fixture');repo.save(payload(row))
    enriched=dict(row,official_text={'text':'Keep this publisher text'})
    refresh=dict(row,excerpt='Updated excerpt',last_seen_at='2099-01-01T00:00:00+00:00')
    original=news_context.story_context;entered=threading.Event();finish=threading.Event()
    def delayed(value):
        if value.get('excerpt')=='Updated excerpt' and not entered.is_set():
            entered.set();assert finish.wait(5)
        return original(value)
    monkeypatch.setattr(news_context,'story_context',delayed)
    with ThreadPoolExecutor(max_workers=1) as pool:
        task=pool.submit(repo.save,payload(refresh))
        try:
            assert entered.wait(3)
            repo.save(payload(enriched))
        finally:finish.set()
        task.result(timeout=5)
    saved=repo.load()['articles'][row['id']]
    assert saved['official_text']==enriched['official_text'] and saved['excerpt']=='Updated excerpt'


def test_legacy_news_migration_is_atomic_idempotent_and_nondestructive():
    import news_repository as repo
    row=item(slug='legacy-fixture');archive=payload(row)
    with database() as db:
        for statement in [
            'CREATE TABLE news_articles (id TEXT PRIMARY KEY,published TEXT,publisher TEXT,payload TEXT)',
            'CREATE TABLE news_entities (article_id TEXT,symbol TEXT,PRIMARY KEY(article_id,symbol))',
            'CREATE TABLE news_search (id TEXT PRIMARY KEY,title TEXT,excerpt TEXT,direction TEXT,headline_group TEXT,topics TEXT)',
            'CREATE TABLE news_meta (id TEXT PRIMARY KEY,payload TEXT)']:db.execute(statement)
        db.execute('INSERT INTO news_articles VALUES (?,?,?,?)',(row['id'],row['published_at'],row['publisher'],json.dumps(row)))
        meta=dict(archive);meta.pop('articles')
        db.execute('INSERT INTO news_meta VALUES (?,?)',('archive',json.dumps(meta)))
    assert repo.load()['articles'][row['id']]==row
    repo.init();assert len(repo.load()['articles'])==1
    with database() as db:
        assert db.execute('SELECT count(*) FROM news_articles').fetchone()[0]==1
    token=lease('after-migration',5);assert token;unlock('after-migration',token)


def test_unrelated_database_errors_are_not_hidden(monkeypatch):
    import shared_cache
    def corrupt(*a):raise sqlite3.OperationalError('database disk image is malformed')
    monkeypatch.setattr(shared_cache,'lease',corrupt)
    with pytest.raises(sqlite3.OperationalError,match='malformed'):
        cached('corrupt',(),lambda:123)
