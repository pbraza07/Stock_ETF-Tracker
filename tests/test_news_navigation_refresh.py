import ast
from pathlib import Path
from streamlit.testing.v1 import AppTest
import market_news
import news_archive


def test_first_and_last_tabs_match_both_navigation_branches():
    tree=ast.parse(Path('app.py').read_text())
    labels=next(ast.literal_eval(n.value) for n in ast.walk(tree) if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id=='_top_tab_labels' for t in n.targets))
    assert labels[0]=='📰 Market News'
    assert labels[-1]=='🔔 Alerts & Help'
    expected=['news_tab','market_tab','favorite_tab','portfolio_tab','future_tab','compare_tab','sector_tab','recession_tab','quality_tab','alerts_tab']
    matches=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Assign) and isinstance(node.value,ast.Call) and node.value.args and isinstance(node.value.args[0],ast.Name) and node.value.args[0].id=='_top_tab_labels':
            matches.append([t.id for t in node.targets[0].elts])
    assert matches==[expected,expected]
    assert len(labels)==len(expected)


def test_manual_refresh_pulls_all_feeds_even_just_after_refresh(monkeypatch,tmp_path):
    monkeypatch.setenv('MARKETSCOPE_NEWS_ARCHIVE',str(tmp_path/'news.json'))
    # Recent empty archive means automatic refresh is not due.
    news_archive.add([],{})
    fetched=[]
    def fetch(source):
        fetched.append(source['id'])
        now=market_news.utcnow().isoformat()
        return [],dict(source_id=source['id'],name=source['name'],status='EMPTY',attempted_at=now,
                       last_success_at=now,count=0,error='')
    monkeypatch.setattr(market_news,'fetch_source',fetch)
    monkeypatch.setattr(news_archive,'restore',lambda:(True,'Checked archive'))
    monkeypatch.setattr(news_archive,'sync',lambda:(True,'Saved archive'))
    app=AppTest.from_string('from market_news_ui import render_market_news\nrender_market_news()').run()
    assert not app.exception and not fetched
    for _ in range(2):
        app.button(key='refresh_market_news').click().run()
        assert not app.exception
        import time
        from performance_store import get
        until=time.monotonic()+3
        while time.monotonic()<until:
            if len(fetched)>=13*(_+1) and len(news_archive.load()['sources'])==13:break
            time.sleep(.02)
        # Wait for the collector lease to finish before another manual request.
        from performance_store import database
        while time.monotonic()<until:
            with database() as db:busy=db.execute("SELECT 1 FROM leases WHERE key='news:refresh'").fetchone()
            if not busy:break
            time.sleep(.02)
    assert len(fetched)==26
    assert set(fetched)=={s['id'] for s in market_news.SOURCES}
    assert len(news_archive.load()['sources'])==13
