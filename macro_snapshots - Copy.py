"""Read validated last-good macro snapshots without relying on Render's disk."""
from datetime import datetime, timezone
import json
from pathlib import Path
import requests
from macro_data import CACHE_DIR
from persistence import DEFAULT_REPO, DEFAULT_BRANCH

ROOT = Path(__file__).parent / 'data' / 'macro_snapshots'
KEYS = {'USPHCI','RECPROUSM156N','SAHMREALTIME','investing_us_week','trading_economics_us_week'}


def validate_snapshot(value, key):
    if key not in KEYS or value.get('key')!=key or not isinstance(value.get('data'),list):
        raise ValueError('Invalid snapshot envelope')
    stamp=datetime.fromisoformat(value['retrieved_at'])
    if stamp.tzinfo is None or stamp>datetime.now(timezone.utc):raise ValueError('Invalid snapshot retrieval date')
    if key in ('USPHCI','RECPROUSM156N','SAHMREALTIME'):
        if not value['data']:raise ValueError('Empty FRED snapshot')
        for row in value['data']:
            datetime.fromisoformat(row['date'])
            if not float('-inf')<float(row['value'])<float('inf'):raise ValueError('Invalid observation')
            if key=='RECPROUSM156N' and not 0<=float(row['value'])<=100:raise ValueError('Invalid probability')
        value['data']=sorted(value['data'],key=lambda row:row['date'])
    else:
        for row in value['data']:
            stamp=datetime.fromisoformat(row['timestamp'])
            if stamp.tzinfo is None or row['country']!='United States' or row['importance']!=3:raise ValueError('Invalid event')
            for field in ('event','actual','forecast','previous'):assert isinstance(row[field],str)
    return value


def with_snapshot(key, result):
    if result['status'] in ('Updated','Cached'):return result
    candidates=[]
    if result['data']:candidates.append(result)
    path=ROOT/f'{key}.json'
    try:candidates.append(validate_snapshot(json.loads(path.read_text()),key))
    except (OSError,ValueError,KeyError,TypeError,AssertionError):pass
    # This is the user's own saved dataset, not a proxy to bypass provider controls.
    try:
        response=requests.get(f'https://raw.githubusercontent.com/{DEFAULT_REPO}/{DEFAULT_BRANCH}/data/macro_snapshots/{key}.json',timeout=(3,6))
        response.raise_for_status()
        candidate=validate_snapshot(response.json(),key);candidates.append(candidate)
        CACHE_DIR.mkdir(parents=True,exist_ok=True)
        (CACHE_DIR/f'{key}.json').write_text(json.dumps(candidate))
    except (requests.RequestException,OSError,ValueError,KeyError,TypeError,AssertionError):pass
    if not candidates:return result
    best=max(candidates,key=lambda item:item['retrieved_at'])
    return {**best,'status':'Stale cache','error':result.get('error'),'fallback':'Last successful saved snapshot; refresh was not successful'}
