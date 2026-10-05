"""Private shared storage: PostgreSQL in production, SQLite WAL locally.

Only trusted server-produced pickle payloads are stored here. Never expose a
write endpoint or accept serialized input from clients.
"""
import os, sqlite3, pickle, hashlib, time, threading,uuid
_schemas=set()
_schema_lock=threading.RLock()
_pools={}
_pool_lock=threading.Lock()
from pathlib import Path
from contextlib import contextmanager


def state_dir():
    path=Path(os.getenv('MARKETSCOPE_STATE_DIR',str(Path(__file__).parent/'.runtime')))
    path.mkdir(parents=True,exist_ok=True)
    return path

class Connection:
    def __init__(self,conn,postgres=False):self.conn=conn;self.postgres=postgres
    def execute(self,sql,args=()):
        if self.postgres:sql=sql.replace('?', '%s').replace('BEGIN IMMEDIATE','BEGIN')
        return self.conn.execute(sql,args)

def initialize(db,name,create):
    identity=(os.getenv('MARKETSCOPE_DATABASE_URL') or str(state_dir()/'performance.sqlite'),name)
    with _schema_lock:
        if identity in _schemas:return
        lock_id=int(hashlib.sha256(name.encode()).hexdigest()[:15],16)
        if db.postgres:db.execute('SELECT pg_advisory_lock(?)',(lock_id,))
        try:create(db)
        finally:
            if db.postgres:db.execute('SELECT pg_advisory_unlock(?)',(lock_id,))
        _schemas.add(identity)

def _create_objects(db):
    blob='BYTEA' if db.postgres else 'BLOB'
    db.execute(f'CREATE TABLE IF NOT EXISTS objects (key TEXT PRIMARY KEY,value {blob},updated DOUBLE PRECISION,expires DOUBLE PRECISION)')
    db.execute('CREATE TABLE IF NOT EXISTS leases (key TEXT PRIMARY KEY,expires DOUBLE PRECISION,owner TEXT)')
    if db.postgres:db.execute('ALTER TABLE leases ADD COLUMN IF NOT EXISTS owner TEXT')
    elif 'owner' not in {r[1] for r in db.execute('PRAGMA table_info(leases)').fetchall()}:
        db.execute('ALTER TABLE leases ADD COLUMN owner TEXT')

@contextmanager
def database():
    url=os.getenv('MARKETSCOPE_DATABASE_URL')
    if url:
        from psycopg_pool import ConnectionPool
        with _pool_lock:
            if url not in _pools:_pools[url]=ConnectionPool(url,min_size=1,max_size=8,kwargs={'autocommit':True})
            pool=_pools[url]
        raw=pool.getconn()
    else:
        raw=sqlite3.connect(state_dir()/'performance.sqlite',timeout=30,isolation_level=None)
        raw.execute('PRAGMA journal_mode=WAL');raw.execute('PRAGMA busy_timeout=30000')
    db=Connection(raw,bool(url))
    try:
        initialize(db,'objects-v56',_create_objects)
        yield db
    finally:
        if url:pool.putconn(raw)
        else:raw.close()

def key_for(namespace,inputs):
    return namespace+':'+hashlib.sha256(pickle.dumps(inputs,protocol=5)).hexdigest()

def get(key):
    with database() as db:row=db.execute('SELECT value,updated,expires FROM objects WHERE key=?',(key,)).fetchone()
    return (pickle.loads(bytes(row[0])),row[1],row[2]) if row else None

def put(key,value,ttl=3600):
    now=time.time()
    with database() as db:
        db.execute('INSERT INTO objects VALUES (?,?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated=excluded.updated,expires=excluded.expires',(key,pickle.dumps(value,protocol=5),now,now+ttl))

def lease(key,seconds=120):
    token=uuid.uuid4().hex
    with database() as db:
        row=db.execute('INSERT INTO leases (key,expires,owner) VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET expires=excluded.expires,owner=excluded.owner WHERE leases.expires < ? RETURNING key',(key,time.time()+seconds,token,time.time())).fetchone()
        return token if row else None

def unlock(key,token):
    with database() as db:db.execute('DELETE FROM leases WHERE key=? AND owner=?',(key,token))


def prune():
    # Keep stale source data for seven days; report artifacts for one day after expiry.
    with database() as db:
        db.execute('DELETE FROM objects WHERE expires < ?',(time.time()-7*86400,))
        db.execute('DELETE FROM objects WHERE key LIKE ? AND expires < ?',('report-v51156-%',time.time()))
        db.execute('DELETE FROM leases WHERE expires < ?',(time.time()-3600,))
