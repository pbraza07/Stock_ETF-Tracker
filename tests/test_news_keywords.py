import re
import pytest
from news_keywords import classify_clause, library_rows
from news_context import story_context, impact_html

U=[('NVDA','NVIDIA','Technology'),('AAPL','Apple','Technology')]

@pytest.mark.parametrize('words,direction',[
 ('beats earnings estimates','bullish'),('misses revenue consensus','bearish'),
 ('raises full-year profit guidance','bullish'),('cuts earnings outlook','bearish'),
 ('reports narrower losses','bullish'),('losses narrowed','bullish'),
 ('losses widened','bearish'),('revenue grew','bullish'),
 ('earnings missed estimates','bearish'),('files for bankruptcy','bearish'),
 ('reduces debt','bullish'),('announces a share buyback','bullish'),
 ('suspends its dividend','bearish'),('wins FDA approval','bullish'),
 ('credit rating downgraded','bearish'),('reaffirms guidance','unclear'),
 ('announces layoffs','unclear'),('announces a merger','unclear'),
 ('does not cut guidance','unclear'),('may raise guidance','unclear'),
 ('supplier cuts profit guidance','unclear'),('shares surge?','unclear'),
 ('fails to beat expectations','unclear'),("doesn’t miss estimates",'unclear'),
])
def test_subject_bound_phrases(words,direction):
    assert classify_clause('Stocks '+words)['direction']==direction

def test_library_patterns_compile_and_are_inspectable():
    assert len(library_rows())>=40
    for row in library_rows():re.compile(row['pattern'])
    assert {x['indicator'] for x in library_rows()}=={'Green','Red','Neutral'}

def test_company_sector_and_evidence_visible():
    c=story_context({'title':'NVIDIA beats earnings estimates','excerpt':''},U)
    assert c['stocks'][0]['matches'][0]['phrase']=='beats earnings estimates'
    assert 'NVIDIA (NVDA) · Technology' in impact_html(c)
    assert c['sectors'][0]['direction']=='unclear'

def test_conflict_is_neutral_display():
    c=story_context({'title':'NVIDIA beats earnings estimates but NVIDIA cuts guidance','excerpt':''},U)
    assert c['stocks'][0]['direction']=='mixed'
    assert 'Neutral / conflicting evidence' in impact_html(c)

def test_conjunction_and_uncertainty():
    for title,d in [('NVIDIA beats estimates and cuts guidance','mixed'),
                    ('NVIDIA may beat estimates and raise guidance','unclear'),
                    ('NVIDIA beats estimates and Apple misses estimates','bullish')]:
        c=story_context({'title':title,'excerpt':''},U)
        assert c['stocks'][0]['direction']==d

def test_unknown_entity_not_invented():
    c=story_context({'title':'Unknown Company beats estimates','excerpt':''},U)
    assert not c['stocks'] and not c['sectors']

def test_macro_and_sector_independent():
    c=story_context({'title':'Inflation cools','excerpt':''},U)
    assert c['market']['direction']=='bullish' and not c['stocks']
    c=story_context({'title':'Technology stocks plunge','excerpt':''},U)
    assert c['sectors'][0]['direction']=='bearish'
    assert c['market']['direction']=='unclear'
