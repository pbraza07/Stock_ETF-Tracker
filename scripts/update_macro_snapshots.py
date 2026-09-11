"""Commit only successful provider downloads; leave prior snapshots untouched."""
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from recession_indicators import load_series
from macro_snapshots import ROOT, validate_snapshot


def save_result(key,result,directory=ROOT):
    if result['status']!='Updated':return False
    payload={k:result[k] for k in ('data','retrieved_at','source')}
    payload['key']=key
    validate_snapshot(payload,key)
    directory.mkdir(parents=True,exist_ok=True)
    path=directory/f'{key}.json';temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(payload,indent=2,allow_nan=False)+'\n');temporary.replace(path)
    return True


def main():
    failed=[]
    for key in ('USPHCI','RECPROUSM156N','SAHMREALTIME'):
        result=load_series(key,True)
        if not save_result(key,result):failed.append(key)
        print(key,result['status'],result.get('error') or '')
    if failed:
        print('::warning::No fresh data for '+', '.join(failed)+'; prior snapshots preserved.')
    return 1 if failed else 0

if __name__=='__main__':raise SystemExit(main())
