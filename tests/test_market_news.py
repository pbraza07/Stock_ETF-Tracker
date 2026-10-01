from datetime import timedelta
import json
from pathlib import Path
from urllib.parse import quote

import pytest
from market_news import SOURCES, parse_feed, make_item, classify, canonical_url, utcnow, official_release
import news_archive as archive

SOURCE=next(s for s in SOURCES if s['id']=='bbc')


def item(title='Stocks rise after earnings',slug='story',at=None):
    return make_item(title,' '.join('word'+str(n) for n in range(60)),f'https://www.bbc.com/{slug}',
                     (at or utcnow()).isoformat(),SOURCE)


def test_rss_sanitizes_short_summary_and_uses_publication_not_fetch_date():
    data=b'''<rss><channel><item><title>Stocks rise</title><link>https://www.bbc.com/a?utm_source=feed</link>
    <description>&lt;p&gt;Earnings improve&lt;/p&gt;&lt;script&gt;evil()&lt;/script&gt;</description>
    <pubDate>Thu, 01 Oct 2026 09:00:00 -0400</pubDate></item></channel></rss>'''
    row=parse_feed(data,SOURCE,'2026-10-02T00:00:00+00:00')[0]
    assert row['published_at']=='2026-10-01T13:00:00+00:00'
    assert row['last_seen_at']=='2026-10-02T00:00:00+00:00'
    assert row['url']=='https://www.bbc.com/a'
    assert 'evil' not in row['excerpt']
    assert len(row['summary'])==3
    assert len(item()['excerpt'].split())==25


def test_atom_and_undated_news():
    xml=b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>GDP report</title>
    <link href="https://www.bbc.com/a"/><summary>Economic release</summary></entry></feed>'''
    row=parse_feed(xml,SOURCE)[0]
    assert row['published_at'] is None
    from market_news_ui import filtered
    payload=archive.empty();payload['articles'][row['id']]=row
    assert filtered(payload,7)==[]
    assert len(filtered(payload,None))==1


@pytest.mark.parametrize('url',['javascript:alert(1)','https://bbc.com.evil.com/x','https://user:pass@bbc.com/a','http://127.0.0.1/x','https://bbc.com:123/x'])
def test_untrusted_links_rejected(url):
    assert canonical_url(url,SOURCE['domains'])==''


@pytest.mark.parametrize('data',[b'<html>blocked</html>',b'<!DOCTYPE rss [<!ENTITY x "x">]><rss/>',b'x'*2_000_001])
def test_bad_xml_rejected(data):
    with pytest.raises(ValueError):parse_feed(data,SOURCE)


@pytest.mark.parametrize('title,direction',[
    ('Stocks rise on earnings','bullish'),('Nasdaq plunges after report','bearish'),
    ('Stocks rise but inflation surges','mixed'),('Stocks may rise after Fed decision','unclear'),
    ('Stocks do not rise','unclear'),('Will stocks rise?','unclear'),
    ('Inflation eases in September','bullish'),('Oil prices rise','unclear'),
    ('Fed cuts rates','unclear'),('Acme lowers profit guidance','bearish')])
def test_direction_is_contextual_and_abstains(title,direction):
    analysis=classify(title)
    assert analysis['direction']==direction
    assert analysis['confidence']=='LOW'


def test_archive_retains_older_news_and_agency_text_and_upserts_urls(tmp_path):
    path=tmp_path/'news.json'
    a=item();a['first_seen_at']=a['last_seen_at']='2026-09-01T00:00:00+00:00'
    a['official_text']={'text':'Agency release'}
    archive.add([a],{},path)
    b=item(slug='other');updated={**a,'last_seen_at':'2026-10-01T00:00:00+00:00'}
    updated.pop('official_text')
    archive.add([updated,b],{},path)
    archive.add([],{'bbc':{'status':'UNAVAILABLE','attempted_at':'2026-10-02T00:00:00+00:00'}},path)
    result=archive.load(path)
    assert len(result['articles'])==2
    assert result['articles'][a['id']]['first_seen_at']=='2026-09-01T00:00:00+00:00'
    assert result['articles'][a['id']]['official_text']['text']=='Agency release'
    assert result['articles'][a['id']]['last_seen_at']=='2026-10-01T00:00:00+00:00'


def test_corrupt_archive_is_not_overwritten(tmp_path):
    path=tmp_path/'news.json';path.write_text('BROKEN')
    with pytest.raises(ValueError):archive.add([item()],{},path)
    assert path.read_text()=='BROKEN'


def test_source_failure_preserves_last_success(tmp_path):
    path=tmp_path/'news.json'
    archive.add([],{ 'bbc':dict(status='OK',last_success_at='2026-09-01',attempted_at='2026-09-01')},path)
    archive.add([],{ 'bbc':dict(status='UNAVAILABLE',attempted_at='2026-10-01')},path)
    assert archive.load(path)['sources']['bbc']['last_success_at']=='2026-09-01'


def test_concurrent_additions_do_not_drop_articles(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    path=tmp_path/'news.json'
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda n:archive.add([item(slug=str(n))],{},path),range(20)))
    assert len(archive.load(path)['articles'])==20


def test_github_conflict_reloads_and_merges_remote(monkeypatch,tmp_path):
    path=tmp_path/'news.json';a=item();b=item(slug='other')
    archive.add([a],{},path)
    remote=archive.empty();remote['articles'][b['id']]=b
    reads=iter([(archive.empty(),'sha1','https://api.github.com/x',{},'main'),(remote,'sha2','https://api.github.com/x',{},'main')])
    monkeypatch.setattr(archive,'github_settings',lambda:('r','main','token'))
    monkeypatch.setattr(archive,'github_read',lambda **k:next(reads))
    posted=[]
    class Response:
        def __init__(self,status):self.status_code=status
        def raise_for_status(self):assert self.status_code==200
    def put(url,**kwargs):
        posted.append(kwargs['json']);return Response(409 if len(posted)==1 else 200)
    monkeypatch.setattr(archive.requests,'put',put)
    assert archive.sync(path)[0]
    import base64
    final=json.loads(base64.b64decode(posted[-1]['content']))
    assert len(final['articles'])==2 and posted[-1]['sha']=='sha2'


def test_no_full_commercial_article_fetch():
    with pytest.raises(ValueError):official_release(item())


def test_feed_outage_returns_status_not_fake_articles(monkeypatch):
    import market_news
    def fail(*args):raise TimeoutError()
    monkeypatch.setattr(market_news,'bounded_get',fail)
    rows,statuses=market_news.collect([SOURCE])
    assert not rows and statuses['bbc']['status']=='UNAVAILABLE'


def test_recent_and_duplicate_overview():
    from market_news_ui import filtered,overview
    fresh=item();same={**fresh,'id':'other'};old=item(slug='old',at=utcnow()-timedelta(days=20))
    payload=archive.empty();payload['articles']={r['id']:r for r in [fresh,same,old]}
    rows=filtered(payload,7)
    assert len(rows)==2
    assert overview(rows)[0]['bullish']==1
    assert filtered(payload,7,publishers=[])==[]


def test_release_integration_and_archive_exclusion():
    app=Path('app.py').read_text()
    assert '"📰 Market News"' in app
    assert app.count('quality_tab, alerts_tab = st.tabs(')==2
    assert 'if news_tab.open:' in app
    from scripts.package_release import LIVE_FILES
    assert 'data/market_news_archive.json' in LIVE_FILES
    assert 'market_news' in Path('.github/workflows/update_market_news.yml').read_text()


def test_ui_cached_archive_can_open_reader(monkeypatch,tmp_path):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv('MARKETSCOPE_NEWS_ARCHIVE',str(tmp_path/'news.json'))
    archive.add([item()],{'bbc':{'status':'OK','attempted_at':utcnow().isoformat(),'count':1}})
    app=AppTest.from_string('from market_news_ui import render_market_news\nrender_market_news()').run()
    assert not app.exception
    buttons=[b for b in app.button if str(b.key).startswith('news_read_')]
    assert len(buttons)==1
    buttons[0].click().run()
    assert not app.exception
    assert any('feed excerpt' in x.value.lower() for x in app.markdown)
