from pathlib import Path
from news_context import story_context,story_summary,impact_html

UNIVERSE=[('NVDA','NVIDIA','Technology'),('AAPL','Apple','Technology')]

def story(title,excerpt=''):
    return {'title':title,'excerpt':excerpt}

def test_company_signal_does_not_become_sector_or_market_signal():
    c=story_context(story('NVIDIA shares surge'),UNIVERSE)
    assert c['stocks'][0]['direction']=='bullish'
    assert c['sectors'][0]['direction']=='unclear'
    assert c['market']['direction']=='unclear'

def test_opposing_companies_are_assessed_separately():
    c=story_context(story('NVIDIA raises profit guidance while Apple cuts profit guidance'),UNIVERSE)
    assert {x['name']:x['direction'] for x in c['stocks']}=={'NVDA':'bullish','AAPL':'bearish'}
    assert c['market']['direction']=='unclear'

def test_broad_market_story_does_not_invent_stock():
    c=story_context(story('Stocks fall as bond selloff eases','Investors reacted to weekly jobs data.'),UNIVERSE)
    assert c['market']['direction']=='bearish'
    assert c['stocks']==[] and c['sectors']==[]
    html=impact_html(c)
    assert 'Not identified' in html and 'Market:' in html and 'Stock:' in html and 'Sector:' in html

def test_sector_move_is_not_a_broad_market_move():
    c=story_context(story('Technology stocks rise'),UNIVERSE)
    assert c['sectors'][0]['direction']=='bullish'
    assert c['market']['direction']=='unclear'

def test_supplier_not_assigned_to_mentioned_customer():
    c=story_context(story('Apple supplier cuts profit guidance'),UNIVERSE)
    assert c['stocks'][0]['direction']=='unclear'

def test_ambiguous_news_stays_neutral():
    c=story_context(story('NVIDIA shares may rise'),UNIVERSE)
    assert c['stocks'][0]['direction']=='unclear'

def test_story_summary_excludes_generic_boilerplate():
    r=story('Stocks fall','Stocks moved lower after weekly jobs data.')
    r['summary']=['irrelevant','Generic risk appetite commentary','Headline rule']
    assert story_summary(r)=='Stocks moved lower after weekly jobs data.'
    assert 'No additional description' in story_summary(story('News headline'))

def test_preview_css_enforces_five_lines_and_reader_remains_available():
    ui=Path('market_news_ui.py').read_text()
    assert '-webkit-line-clamp:5' in ui and 'max-height:7.5em' in ui
    assert "story_summary(row)" in ui and "read_story(row)" in ui

def test_exchange_mention_not_broad_market_signal():
    c=story_context(story('NASDAQ:NVDA raises profit guidance'),UNIVERSE)
    assert c['market']['direction']=='unclear'
