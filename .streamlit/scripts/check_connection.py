"""Single-pass public connection diagnostics. Never retries HTTP 429."""
import argparse
import json
from datetime import datetime,timezone
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from urllib.parse import urlsplit

def check(base):
    parsed=urlsplit(base)
    if parsed.scheme not in ('http','https') or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Use the public app URL without credentials, query or fragment.')
    rows=[]
    for path in ('/_stcore/health','/_stcore/host-config'):
        row={'utc':datetime.now(timezone.utc).isoformat(),'path':path}
        try:
            response=urlopen(Request(base.rstrip('/')+path),timeout=20)
        except HTTPError as exc:response=exc
        except (URLError,TimeoutError) as exc:
            row.update(status=None,error_type=type(exc).__name__);rows.append(row);break
        with response:
            row.update(status=response.status,headers={key:response.headers[key] for key in ('Server','Retry-After','rndr-id','CF-RAY','x-render-origin-server') if key in response.headers})
            # Do not save cookies or page content.
        rows.append(row)
        if row['status']==429:break
    return rows

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('url');args=parser.parse_args()
    rows=check(args.url);print(json.dumps(rows,indent=2))
    raise SystemExit(0 if len(rows)==2 and all(r['status']==200 for r in rows) else 1)
