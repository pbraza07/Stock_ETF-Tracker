from datetime import timedelta
from streamlit.testing.v1 import AppTest
from market_news import make_item, SOURCES, utcnow
from news_stock_index import stock_index
import news_archive

SOURCE=next(s for s in SOURCES if s['id']=='bbc')
U=[('NVDA','NVIDIA','Technology'),('AAPL','Apple','Technology'),('CAT','Caterpillar','Industrials')]

def item(title,slug,age=0,excerpt=''):
    return make_item(title,excerpt,'https://www.bbc.com/'+slug,
                     (utcnow()-timedelta(days=age)).isoformat(),SOURCE)

def test_index_includes_old_neutral_excerpt_and_multiple_company_references():
    rows=[item('NVIDIA outlook unchanged','old',400),
          item('Industry news','two',excerpt='Apple and NVIDIA report this week.'),
          item('CAT scan research','ambiguous'),item('$CAT meeting','explicit')]
    payload={'articles':{r['id']:r for r in rows}}
    index=stock_index(payload,U)
    assert index['NVDA']['article_ids']=={rows[0]['id'],rows[1]['id']}
    assert index['AAPL']['article_ids']=={rows[1]['id']}
    assert index['CAT']['article_ids']=={rows[3]['id']}
    assert stock_index({'articles':{}},U)=={}

def test_stock_selection_resets_filters_and_returns_all_saved_matches(monkeypatch,tmp_path):
    monkeypatch.setenv('MARKETSCOPE_NEWS_ARCHIVE',str(tmp_path/'news.json'))
    rows=[item('NVIDIA old story','old',400),item('NVIDIA new story','new'),
          item('Apple company story','apple'),item('Economic news','macro')]
    news_archive.add(rows,{})
    app=AppTest.from_string('from market_news_ui import render_market_news\nrender_market_news()').run()
    assert not app.exception
    app.text_input(key='news_query').set_value('no matching text').run()
    app.selectbox(key='news_stock').select('NVDA').run()
    assert not app.exception
    assert app.selectbox(key='news_period').value=='All archived news'
    assert app.text_input(key='news_query').value==''
    keys={b.key for b in app.button}
    assert {'news_read_'+r['id'] for r in rows[:2]} <= keys
    assert not {'news_read_'+r['id'] for r in rows[2:]} & keys
    app.selectbox(key='news_stock').select('AAPL').run()
    assert not app.exception
    keys={b.key for b in app.button}
    assert 'news_read_'+rows[2]['id'] in keys
    assert 'news_read_'+rows[0]['id'] not in keys
    app.selectbox(key='news_stock').select('').run()
    assert not app.exception
    assert {'news_read_'+r['id'] for r in rows} <= {b.key for b in app.button}

def test_filter_options_update_after_archive_changes(monkeypatch,tmp_path):
    monkeypatch.setenv('MARKETSCOPE_NEWS_ARCHIVE',str(tmp_path/'news.json'))
    news_archive.add([item('NVIDIA story','nvda')],{})
    app=AppTest.from_string('from market_news_ui import render_market_news\nrender_market_news()').run()
    app.selectbox(key='news_stock').select('NVDA').run()
    news_archive.add([item('Apple story','aapl')],{})
    app.run()
    assert not app.exception
    assert app.selectbox(key='news_stock').value=='NVDA'
    assert any('AAPL' in x for x in app.selectbox(key='news_stock').options)
