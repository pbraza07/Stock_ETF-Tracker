"""Durable bounded jobs with priority aging. Opaque bearer IDs must be kept private.

Tasks are server-created cloudpickle closures only, never untrusted uploads.
Running jobs interrupted by a worker exit become explicit failures; they are not
silently retried. Queued jobs survive restart. PostgreSQL supports external workers.
"""
import os,time,uuid,json,subprocess,sys,threading
import cloudpickle
from performance_store import initialize,database,state_dir,key_for,get,put
_spawn_lock=threading.Lock();_worker=None

def _create_schema(db):
    blob='BYTEA' if db.postgres else 'BLOB'
    db.execute(f'''CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, state TEXT, created DOUBLE PRECISION,
      heartbeat DOUBLE PRECISION, progress TEXT, task {blob}, result {blob}, error TEXT, owner TEXT,priority INTEGER NOT NULL DEFAULT 10)''')
    if db.postgres:db.execute('ALTER TABLE jobs ADD COLUMN IF NOT EXISTS priority INTEGER NOT NULL DEFAULT 10')
    elif 'priority' not in {r[1] for r in db.execute('PRAGMA table_info(jobs)').fetchall()}:db.execute('ALTER TABLE jobs ADD COLUMN priority INTEGER NOT NULL DEFAULT 10')
    db.execute('CREATE INDEX IF NOT EXISTS jobs_state_created ON jobs(state,priority,created)')

def init():
    with database() as db:initialize(db,"jobs-v56",_create_schema)


def ensure_worker():
    global _worker
    if os.getenv('MARKETSCOPE_EXTERNAL_WORKER','0')=='1':return
    with _spawn_lock:
        if _worker is None or _worker.poll() is not None:
            _worker=subprocess.Popen([sys.executable,'-m','performance_worker'],cwd=os.path.dirname(__file__),env=os.environ.copy())

def submit(task,owner=None,priority=10):
    init();payload=cloudpickle.dumps(task);token=uuid.uuid4().hex
    identity=key_for('job-submit-v51156',(owner,payload))
    previous=get(identity) if owner else None
    if previous and previous[2]>time.time():
        prior=poll(previous[0])
        if prior and prior['state'] in ('queued','running','done'):return previous[0]
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.postgres:db.execute('LOCK TABLE jobs IN SHARE ROW EXCLUSIVE MODE')
        count=db.execute("SELECT count(*) FROM jobs WHERE state IN ('queued','running')").fetchone()[0]
        if count>=int(os.getenv('MARKETSCOPE_MAX_QUEUED_JOBS','20')):
            db.execute('ROLLBACK');raise RuntimeError('Calculation queue is full. Try again shortly; existing jobs are retained.')
        if owner and db.execute("SELECT count(*) FROM jobs WHERE owner=? AND state IN ('queued','running')",(owner,)).fetchone()[0]>=2:
            db.execute('ROLLBACK');raise RuntimeError('You already have two queued or running calculations.')
        db.execute('INSERT INTO jobs (id,state,created,heartbeat,progress,task,result,error,owner,priority) VALUES (?,?,?,?,?,?,?,?,?,?)',(token,'queued',time.time(),time.time(),json.dumps([0,1,'Queued for calculation']),payload,None,None,owner or token,int(priority)))
        db.execute('COMMIT')
    if owner:put(identity,token,900)
    ensure_worker();return token

class StoredFuture:
    def __init__(self,token):self.token=token
    def done(self):
        with database() as db:row=db.execute('SELECT state FROM jobs WHERE id=?',(self.token,)).fetchone()
        return not row or row[0] in ('done','failed','cancelled')
    def result(self,timeout=None):
        start=time.monotonic()
        while True:
            with database() as db:row=db.execute('SELECT state,result,error FROM jobs WHERE id=?',(self.token,)).fetchone()
            if not row:raise RuntimeError('Job expired or was released.')
            if row[0]=='done':return cloudpickle.loads(bytes(row[1]))
            if row[0] in ('failed','cancelled'):raise RuntimeError(row[2] or 'Calculation cancelled.')
            if timeout is not None and time.monotonic()-start>timeout:raise TimeoutError('Calculation still running.')
            time.sleep(.1)

def poll(token):
    init()
    with database() as db:row=db.execute('SELECT progress,state FROM jobs WHERE id=?',(str(token),)).fetchone()
    if not row:return None
    ensure_worker()
    return {'progress':tuple(json.loads(row[0])),'future':StoredFuture(token),'state':row[1]}

def release(token):
    # Keep completed results for private reconnect/recovery for 24h.
    pass

def cancel(token):
    with database() as db:db.execute("UPDATE jobs SET state='cancelled',error='Cancelled by user',task=NULL WHERE id=? AND state IN ('queued','running')",(token,))

def run_one():
    init()
    with database() as db:
        db.execute("UPDATE jobs SET state='failed',error='Worker interrupted. Submit again to retry.',task=NULL WHERE state='running' AND heartbeat < ?",(time.time()-120,))
        db.execute('DELETE FROM jobs WHERE created < ? AND state NOT IN (?,?)',(time.time()-86400,'queued','running'))
        db.execute('BEGIN IMMEDIATE')
        suffix=' FOR UPDATE SKIP LOCKED' if db.postgres else ''
        row=db.execute("SELECT id,task FROM jobs WHERE state='queued' ORDER BY (priority - (? - created)/300.0),created LIMIT 1"+suffix,(time.time(),)).fetchone()
        if row:db.execute("UPDATE jobs SET state='running',heartbeat=? WHERE id=?",(time.time(),row[0]))
        db.execute('COMMIT')
    if not row:return False
    token,payload=row;stop=threading.Event()
    def heartbeat():
        while not stop.wait(10):
            with database() as db:db.execute('UPDATE jobs SET heartbeat=? WHERE id=?',(time.time(),token))
    thread=threading.Thread(target=heartbeat,daemon=True);thread.start()
    last=[0.]
    def progress(done,total,label):
        if time.monotonic()-last[0]<.25 and done<total:return
        with database() as db:
            state=db.execute('SELECT state FROM jobs WHERE id=?',(token,)).fetchone()
            if not state or state[0]=='cancelled':raise RuntimeError('Calculation cancelled.')
            db.execute('UPDATE jobs SET progress=?,heartbeat=? WHERE id=?',(json.dumps([int(done),int(total),str(label)]),time.time(),token))
        last[0]=time.monotonic()
    try:
        result=cloudpickle.loads(bytes(payload))(progress)
        with database() as db:db.execute("UPDATE jobs SET state='done',result=?,task=NULL WHERE id=? AND state='running'",(cloudpickle.dumps(result),token))
    except Exception as exc:
        with database() as db:db.execute("UPDATE jobs SET state='failed',error=?,task=NULL WHERE id=? AND state='running'",(str(exc)[:1000],token))
    finally:stop.set();thread.join(timeout=1)
    return True
