"""Scheduled collector; never purges history when a source is unavailable."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from market_news import collect
import news_archive

if __name__=='__main__':
    rows,statuses=collect(progress=lambda done,total,name:print(f'{done}/{total}: {name}',flush=True))
    payload=news_archive.add(rows,statuses)
    ok,message=news_archive.sync()
    print(message)
    for s in statuses.values():print(f"{s['name']}: {s['status']} ({s['count']} items) {s['error']}")
    print(f'{len(payload["articles"])} articles retained in archive')
    if not ok or not any(s['status']=='OK' for s in statuses.values()):sys.exit(1)
