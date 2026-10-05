"""Append/update news archive with atomic saves and conflict-safe GitHub mirroring."""
from __future__ import annotations
import base64
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile
import threading

import requests
from market_news import SOURCE_BY_ID, utcnow

REMOTE_PATH='data/market_news_archive.json'
_LOCK=threading.RLock()


def archive_path():
    return Path(os.environ.get('MARKETSCOPE_NEWS_ARCHIVE', Path(__file__).parent/REMOTE_PATH))


def empty():
    return dict(schema=1,articles={},sources={},updated_at=None)


def validate(payload):
    if not isinstance(payload,dict) or payload.get('schema')!=1 or not isinstance(payload.get('articles'),dict) or not isinstance(payload.get('sources'),dict):
        raise ValueError('Invalid news archive; refusing to overwrite it')
    for key, row in payload['articles'].items():
        if not isinstance(row,dict) or row.get('id')!=key or row.get('source_id') not in SOURCE_BY_ID or not isinstance(row.get('summary'),list) or len(row['summary'])!=3:
            raise ValueError('Invalid archived article')
    return payload


def load(path=None):
    if path is None:
        from news_repository import load as database_load
        stored=database_load()
        if stored is not None:return validate(stored)
    path=Path(path or archive_path())
    if not path.exists():return empty()
    payload=validate(json.loads(path.read_text(encoding='utf-8')))
    # Import the existing file without deleting or rewriting it.
    if path==archive_path():
        from news_repository import save as database_save
        database_save(payload)
    return payload


def merge(left,right):
    result=empty()
    for payload in (validate(left),validate(right)):
        for key,row in payload['articles'].items():
            old=result['articles'].get(key)
            if old:
                newer,older=(row,old) if row['last_seen_at']>=old['last_seen_at'] else (old,row)
                row={**older,**newer,'first_seen_at':min(old['first_seen_at'],row['first_seen_at'])}
                # Optional agency text survives subsequent RSS refreshes.
                if older.get('official_text') and not newer.get('official_text'):
                    row['official_text']=older['official_text']
            result['articles'][key]=dict(row)
        for key,status in payload['sources'].items():
            old=result['sources'].get(key,{})
            if status.get('attempted_at','')>=old.get('attempted_at',''):
                result['sources'][key]={**old,**status}
        result['updated_at']=max(filter(None,[result['updated_at'],payload.get('updated_at')]),default=None)
    return result


@contextmanager
def locked(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    with _LOCK, open(str(path)+'.lock','a') as lock:
        try:
            import fcntl
        except ImportError:
            fcntl=None
        if fcntl:fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
        try:yield
        finally:
            if fcntl:fcntl.flock(lock.fileno(),fcntl.LOCK_UN)


def save(payload,path=None):
    if path is None:
        from news_repository import save as database_save,load as database_load
        if database_load() is None and archive_path().exists():
            database_save(validate(json.loads(archive_path().read_text(encoding="utf-8"))))
        database_save(validate(payload))
        return database_load()
    path=Path(path or archive_path())
    with locked(path):
        payload=merge(load(path),payload)
        fd,tmp=tempfile.mkstemp(prefix='news-',suffix='.tmp',dir=path.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as output:
                json.dump(payload,output,ensure_ascii=False,indent=2)
                output.flush();os.fsync(output.fileno())
            os.replace(tmp,path)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
    return payload


def add(items,statuses,path=None):
    payload=empty();payload.update(articles={item['id']:item for item in items},sources=statuses,updated_at=utcnow().isoformat())
    return save(payload,path)


def github_settings():
    repo=os.environ.get('MARKETSCOPE_GITHUB_REPO','pbraza07/Stock_ETF-Tracker')
    branch=os.environ.get('MARKETSCOPE_GITHUB_BRANCH','main')
    token=os.environ.get('MARKETSCOPE_GITHUB_TOKEN','').strip()
    return repo,branch,token


def github_read(token_required=False):
    repo,branch,token=github_settings()
    if token_required and not token:raise ValueError('GitHub archive writes require MARKETSCOPE_GITHUB_TOKEN')
    url=f'https://api.github.com/repos/{repo}/contents/{REMOTE_PATH}'
    headers={'Accept':'application/vnd.github+json','User-Agent':'MarketScope-News'}
    if token:headers['Authorization']=f'Bearer {token}'
    response=requests.get(url,headers=headers,params={'ref':branch},timeout=(3,8))
    if response.status_code==404:
        # Only authenticated write flow may create a missing file; permission errors on PUT remain visible.
        return empty(),None,url,headers,branch
    response.raise_for_status()
    data=response.json()
    if data.get('encoding')=='base64':
        payload=validate(json.loads(base64.b64decode(data['content'])))
    else:
        # GitHub omits inline base64 for larger files. Raw media still uses the
        # authenticated Contents endpoint, not a redirected credential-bearing URL.
        raw=requests.get(url,headers={**headers,'Accept':'application/vnd.github.raw+json'},
                         params={'ref':branch},timeout=(3,12))
        raw.raise_for_status();payload=validate(raw.json())
    return payload,data['sha'],url,headers,branch


def restore(path=None):
    try:
        payload,_,_,_,_=github_read()
        if payload['articles']:save(payload,path)
        return True,'GitHub archive checked'
    except Exception as exc:
        return False,'GitHub archive could not be read ('+type(exc).__name__+'); local history retained'


def sync(path=None):
    if not github_settings()[2]:
        return False,'Saved on this server. For durable storage, set MARKETSCOPE_NEWS_ARCHIVE on a persistent disk or configure MARKETSCOPE_GITHUB_TOKEN.'
    for attempt in range(3):
        try:
            remote,sha,url,headers,branch=github_read(token_required=True)
            payload=save(merge(remote,load(path)),path)
            body={'message':'Archive MarketScope news [skip render]','branch':branch,
                  'content':base64.b64encode(json.dumps(payload,ensure_ascii=False,indent=2).encode()).decode()}
            if sha:body['sha']=sha
            response=requests.put(url,headers=headers,json=body,timeout=(3,12))
            if response.status_code in (409,422) and attempt<2:continue
            response.raise_for_status()
            return True,'Saved on server and GitHub'
        except Exception as exc:
            return False,'Saved on server; GitHub sync failed ('+type(exc).__name__+')'
    return False,'Saved on server; concurrent GitHub update prevented mirroring'
