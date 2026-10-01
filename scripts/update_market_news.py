"""Scheduled collector; never purges history when a source is unavailable."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from market_news import collect
import news_archive

if __name__=='__main__':
    rows,statuses=collect(progress=lambda done,total,name:print(f'{done}/{total}: {name}',flush=True))
    payload=news_archive.add(rows,statuses)
    # Bounded background work; the dashboard never blocks on a batch of AI calls.
    import os
    from article_summary import configured, summarize_article
    if configured():
        limit=max(0,min(5,int(os.getenv('MARKETSCOPE_NEWS_SUMMARIES_PER_PULL','3'))))
        pending=sorted((r for r in payload['articles'].values() if not r.get('article_summary')),
                       key=lambda r:r.get('published_at') or '',reverse=True)
        # Rotate failed URLs instead of repeatedly starving other articles.
        pending.sort(key=lambda r:r.get('summary_attempt_at',''))
        from market_news import utcnow
        for row in pending[:limit]:
            updated={**row,'summary_attempt_at':utcnow().isoformat()}
            try:
                updated['article_summary']=summarize_article(row)
                print('Full-article summary saved: '+row['id'])
            except Exception as exc:
                updated['summary_error']=type(exc).__name__
                print('Full-article summary unavailable: '+row['id']+' ('+type(exc).__name__+')')
            news_archive.add([updated],{})
    ok,message=news_archive.sync()
    print(message)
    for s in statuses.values():print(f"{s['name']}: {s['status']} ({s['count']} items) {s['error']}")
    print(f'{len(payload["articles"])} articles retained in archive')
    if not ok or not any(s['status']=='OK' for s in statuses.values()):sys.exit(1)
