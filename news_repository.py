"""Indexed article repository shared by collectors and web processes."""
import json
from performance_store import initialize, database as _database, state_dir

def database():
    # SQLite news analysis/indexing cannot starve source-cache leases or jobs.
    # PostgreSQL keeps the shared service with its normal row-level locking.
    return _database(namespace="news")

def _create_schema(db):
    db.execute('CREATE TABLE IF NOT EXISTS news_articles (id TEXT PRIMARY KEY,published TEXT,publisher TEXT,payload TEXT)')
    db.execute('CREATE INDEX IF NOT EXISTS news_date ON news_articles(published)')
    db.execute('CREATE TABLE IF NOT EXISTS news_entities (article_id TEXT,symbol TEXT,PRIMARY KEY(article_id,symbol))')
    db.execute('CREATE INDEX IF NOT EXISTS news_symbol ON news_entities(symbol,article_id)')
    db.execute('CREATE TABLE IF NOT EXISTS news_search (id TEXT PRIMARY KEY,title TEXT,excerpt TEXT,direction TEXT,headline_group TEXT,topics TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS news_meta (id TEXT PRIMARY KEY,payload TEXT)')
    if not db.postgres and not db.execute("SELECT 1 FROM news_meta WHERE id='archive'").fetchone():
        # One-time, atomic copy of committed legacy news data. Never delete the source.
        legacy=state_dir()/'performance.sqlite'
        if legacy.exists():
            db.execute('ATTACH DATABASE ? AS legacy_news',(str(legacy),))
            try:
                present=db.execute("SELECT 1 FROM legacy_news.sqlite_master WHERE type='table' AND name='news_meta'").fetchone()
                if present and db.execute("SELECT 1 FROM legacy_news.news_meta WHERE id='archive'").fetchone():
                    db.execute('BEGIN IMMEDIATE')
                    try:
                        for table in ('news_articles','news_entities','news_search','news_meta'):
                            exists=db.execute("SELECT 1 FROM legacy_news.sqlite_master WHERE type='table' AND name=?",(table,)).fetchone()
                            if exists:db.execute(f'INSERT OR IGNORE INTO {table} SELECT * FROM legacy_news.{table}')
                        db.execute('COMMIT')
                    except Exception:db.execute('ROLLBACK');raise
            finally:db.execute('DETACH DATABASE legacy_news')

def init():
    with database() as db:initialize(db,"news-v56",_create_schema)


def save(payload,force=False):
    init()
    from news_context import story_context
    from news_archive import merge,empty
    for key,incoming in payload['articles'].items():
        # Optimistic per-article merge: CPU-heavy context analysis never runs
        # while holding a write lock. Re-read after acquiring the lock so a
        # concurrent enrichment is merged rather than overwritten.
        for attempt in range(10):
            with database() as db:
                old=db.execute('SELECT payload FROM news_articles WHERE id=?',(key,)).fetchone()
                indexed=db.execute('SELECT id FROM news_search WHERE id=?',(key,)).fetchone()
            before=old[0] if old else None
            row=(merge(dict(empty(),articles={key:json.loads(before)}),
                       dict(empty(),articles={key:incoming}))['articles'][key] if before else incoming)
            serialized=json.dumps(row,ensure_ascii=False)
            if not force and before==serialized and indexed:break
            context=story_context(row)
            with database() as db:
                db.execute('BEGIN IMMEDIATE')
                try:
                    if db.postgres:db.execute('LOCK TABLE news_articles IN SHARE ROW EXCLUSIVE MODE')
                    latest=db.execute('SELECT payload FROM news_articles WHERE id=?',(key,)).fetchone()
                    if (latest[0] if latest else None)!=before:
                        db.execute('ROLLBACK')
                        continue
                    db.execute('INSERT INTO news_articles VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET published=excluded.published,publisher=excluded.publisher,payload=excluded.payload',
                        (key,row.get('published_at'),row['publisher'],serialized))
                    db.execute('DELETE FROM news_entities WHERE article_id=?',(key,))
                    db.execute('INSERT INTO news_search VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,excerpt=excluded.excerpt,direction=excluded.direction,headline_group=excluded.headline_group,topics=excluded.topics',(key,row['title'],row.get('excerpt',''),context['market']['direction'],row.get('headline_group',key),json.dumps(row.get('analysis',{}).get('topics',[]))))
                    for stock in context['stocks']:
                        symbol=stock.get('symbol') or stock.get('ticker') or stock.get('name')
                        if symbol:db.execute('INSERT INTO news_entities VALUES (?,?) ON CONFLICT DO NOTHING',(key,symbol))
                    db.execute('COMMIT')
                except Exception:db.execute('ROLLBACK');raise
            break
        else:raise RuntimeError('News changed repeatedly during indexing; retry the save.')
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        try:
            if db.postgres:db.execute('LOCK TABLE news_meta IN SHARE ROW EXCLUSIVE MODE')
            old=db.execute("SELECT payload FROM news_meta WHERE id='archive'").fetchone()
            meta=json.loads(old[0]) if old else {'schema':1,'sources':{},'updated_at':None}
            meta=merge(dict(meta,articles={}),dict(empty(),sources=payload['sources'],updated_at=payload.get('updated_at')))
            meta.pop('articles',None)
            db.execute("INSERT INTO news_meta VALUES ('archive',?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",(json.dumps(meta),))
            db.execute('COMMIT')
        except Exception:db.execute('ROLLBACK');raise

def load():
    init()
    with database() as db:
        meta=db.execute("SELECT payload FROM news_meta WHERE id='archive'").fetchone()
        if not meta:return None
        result=json.loads(meta[0]);result['articles']={key:json.loads(value) for key,value in db.execute('SELECT id,payload FROM news_articles').fetchall()}
    return result

def page(symbol=None,limit=20,offset=0):
    init()
    with database() as db:
        if symbol:
            rows=db.execute('SELECT a.payload FROM news_articles a JOIN news_entities e ON a.id=e.article_id WHERE e.symbol=? ORDER BY a.published DESC LIMIT ? OFFSET ?',(symbol,int(limit),int(offset))).fetchall()
        else:rows=db.execute('SELECT payload FROM news_articles ORDER BY published DESC LIMIT ? OFFSET ?',(int(limit),int(offset))).fetchall()
    return [json.loads(row[0]) for row in rows]


def catalog():
    init()
    with database() as db:
        missing=db.execute('SELECT count(*) FROM news_articles a LEFT JOIN news_search s ON a.id=s.id WHERE s.id IS NULL').fetchone()[0]
    from news_context import securities
    from news_keywords import VERSION
    from performance_store import key_for
    version=key_for('news-index',(VERSION,tuple(securities())))
    with database() as db:
        indexed=db.execute("SELECT payload FROM news_meta WHERE id='index-version'").fetchone()
        present=db.execute("SELECT 1 FROM news_meta WHERE id='archive'").fetchone()
    if present and (missing or not indexed or indexed[0]!=version):
        save(load(),force=True)
        with database() as db:db.execute("INSERT INTO news_meta VALUES ('index-version',?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",(version,))
    names={s:(n,c) for s,n,c in securities()}
    with database() as db:
        meta=db.execute("SELECT payload FROM news_meta WHERE id='archive'").fetchone()
        if not meta:return None
        value=json.loads(meta[0])
        value['count']=db.execute('SELECT count(*) FROM news_articles').fetchone()[0]
        value['publishers']=[r[0] for r in db.execute('SELECT DISTINCT publisher FROM news_articles ORDER BY publisher').fetchall()]
        value['stocks']={s:dict(company=names.get(s,(s,'Sector unavailable'))[0],sector=names.get(s,(s,'Sector unavailable'))[1],article_count=n) for s,n in db.execute('SELECT symbol,count(*) FROM news_entities GROUP BY symbol').fetchall()}
    return value


def query_rows(days=7,publishers=None,direction='All',query='',symbol=None,limit=20,offset=0):
    from datetime import timedelta
    from market_news import utcnow
    init();where=[];args=[]
    if days:
        where+=['a.published>=?','a.published<=?'];args +=[(utcnow()-timedelta(days=days)).isoformat(),(utcnow()+timedelta(hours=1)).isoformat()]
    if publishers is not None:
        if not publishers:return 0,[]
        where.append('a.publisher IN ('+','.join('?' for _ in publishers)+')');args+=list(publishers)
    if direction!='All':where.append('s.direction=?');args.append(direction)
    if query:
        # Literal substring matching; escape SQL wildcard characters.
        text=query.lower().replace('!','!!').replace('%','!%').replace('_','!_')
        where.append("LOWER(s.title || ' ' || s.excerpt) LIKE ? ESCAPE '!'");args.append('%'+text+'%')
    if symbol:where.append('EXISTS (SELECT 1 FROM news_entities e WHERE e.article_id=a.id AND e.symbol=?)');args.append(symbol)
    base=' FROM news_articles a JOIN news_search s ON a.id=s.id'+(' WHERE '+' AND '.join(where) if where else '')
    with database() as db:
        count=db.execute('SELECT count(*)'+base,args).fetchone()[0]
        rows=db.execute('SELECT a.payload'+base+' ORDER BY a.published DESC,a.id LIMIT ? OFFSET ?',args+[int(limit),int(offset)]).fetchall()
    return count,[json.loads(r[0]) for r in rows]


def recent_overview():
    from collections import Counter
    from datetime import timedelta
    from market_news import utcnow
    with database() as db:
        rows=db.execute('SELECT s.headline_group,s.direction,s.topics FROM news_articles a JOIN news_search s ON a.id=s.id WHERE a.published>=? AND a.published<=? ORDER BY a.published DESC',((utcnow()-timedelta(days=7)).isoformat(),(utcnow()+timedelta(hours=1)).isoformat())).fetchall()
    unique={key:(direction,topics) for key,direction,topics in rows}
    return Counter(v[0] for v in unique.values()),Counter(t for v in unique.values() for t in json.loads(v[1]))
