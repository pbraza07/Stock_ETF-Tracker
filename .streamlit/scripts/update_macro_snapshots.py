"""Commit only successful provider downloads; leave prior snapshots untouched."""
import json
import os
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor
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
    keys=('USPHCI','RECPROUSM156N','SAHMREALTIME')
    print('FRED_API_KEY configured:', bool(os.getenv('FRED_API_KEY','').strip()), flush=True)
    summary=['## Macro snapshot refresh', '', '| Series | Result | Details |', '| --- | --- | --- |']
    def collect(key):
        try:
            result=load_series(key,True,background=True)
            saved=save_result(key,result)
            detail=result.get('error') or result.get('diagnostic') or 'Validated provider download saved'
            return key,saved,result['status'],detail
        except Exception as exc:
            # Do not print exception strings: request URLs can contain a secret.
            return key,False,'Failed',type(exc).__name__
    with ThreadPoolExecutor(max_workers=3) as pool:
        for key,saved,status,detail in pool.map(collect,keys):
            if not saved:failed.append(key)
            print(key,status,detail,flush=True)
            summary.append(f'| {key} | {status} | {detail} |')
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as file:
            file.write('\n'.join(summary)+'\n\nOld snapshots are preserved on failure; stale data is never marked fresh.\n')
    if failed:
        print('::warning::No fresh data for '+', '.join(failed)+'; prior snapshots preserved.')
        print('If FRED_API_KEY is not configured, add it in repository Settings > Secrets and variables > Actions. A Render environment variable does not configure GitHub Actions.')
    return 1 if failed else 0

if __name__=='__main__':raise SystemExit(main())
