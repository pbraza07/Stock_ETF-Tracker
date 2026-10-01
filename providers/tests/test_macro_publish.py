import json
import subprocess
from pathlib import Path
from scripts import publish_macro_snapshots as publisher


def git(repo,*args):
    return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.DEVNULL,text=True).strip()


def put(repo,key,day,value):
    p=repo/'data/macro_snapshots'/f'{key}.json';p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps({'key':key,'retrieved_at':f'2026-01-{day:02}T00:00:00+00:00',
                            'source':'https://fred.stlouisfed.org','data':[{'date':'2025-12-01','value':value}]}))


def setup(tmp_path):
    origin=tmp_path/'origin';origin.mkdir();git(origin,'init','--bare','--initial-branch=main')
    first=tmp_path/'first';git(tmp_path,'clone',str(origin),str(first))
    for key,value in [('user.name','Test'),('user.email','test@example.com')]:git(first,'config',key,value)
    (first/'app.txt').write_text('original');git(first,'add','.');git(first,'commit','-m','base');git(first,'push','origin','main')
    stale=tmp_path/'stale';git(tmp_path,'clone',str(origin),str(stale))
    return origin,first,stale


def test_add_add_conflict_reproduced_and_publisher_preserves_newer_remote(tmp_path):
    origin,first,stale=setup(tmp_path)
    put(first,'USPHCI',3,153);(first/'app.txt').write_text('new app')
    git(first,'add','.');git(first,'commit','-m','concurrent update');git(first,'push','origin','main')
    put(stale,'USPHCI',2,152);put(stale,'SAHMREALTIME',2,.3)
    publisher.publish(stale)
    git(first,'pull','--ff-only')
    assert json.loads((first/'data/macro_snapshots/USPHCI.json').read_text())['data'][0]['value']==153
    assert (first/'data/macro_snapshots/SAHMREALTIME.json').exists()
    assert (first/'app.txt').read_text()=='new app'
    assert (stale/'app.txt').read_text()=='original'
    publisher.publish(stale) # idempotent, no conflicting commit


def test_remote_moves_during_push_retries_without_losing_files(tmp_path,monkeypatch):
    origin,first,stale=setup(tmp_path)
    put(stale,'RECPROUSM156N',3,2)
    original=publisher.git;triggered=[]
    def race(repo,*args):
        if args[0]=='push' and not triggered:
            triggered.append(True)
            (first/'user_data.txt').write_text('preserve me')
            git(first,'add','.');git(first,'commit','-m','race');git(first,'push','origin','main')
        return original(repo,*args)
    monkeypatch.setattr(publisher,'git',race)
    publisher.publish(stale)
    git(first,'pull','--ff-only')
    assert (first/'user_data.txt').read_text()=='preserve me'
    assert (first/'data/macro_snapshots/RECPROUSM156N.json').exists()
    assert len(git(stale,'worktree','list').splitlines())==1
