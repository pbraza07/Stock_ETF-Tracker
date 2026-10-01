from html.parser import HTMLParser
import pandas as pd
import pytest
from recession_interactive import interactive_html

class Scripts(HTMLParser):
    def __init__(self): super().__init__(); self.sources=[]; self.inline=[]; self.active=False
    def handle_starttag(self,tag,attrs):
        if tag=='script':
            self.active=True; self.inline.append(''); self.sources.extend(v for k,v in attrs if k=='src')
    def handle_data(self,data):
        if self.active: self.inline[-1]+=data
    def handle_endtag(self,tag):
        if tag=='script': self.active=False

@pytest.mark.parametrize('series',['USPHCI','RECPROUSM156N','SAHMREALTIME'])
@pytest.mark.parametrize('years',[None,5,10,20])
def test_interactive_is_self_contained_with_full_history(series,years):
    rows=[{'date':str(d.date()),'value':float(i%20)/10} for i,d in enumerate(pd.date_range('1959-01-01','2026-07-01',freq='MS'))]
    html=interactive_html(series,rows,years)
    parsed=Scripts();parsed.feed(html)
    assert not parsed.sources
    assert len(parsed.inline)==3
    assert 'Plotly.newPlot' in parsed.inline[-1]
    assert 'scrollZoom' in parsed.inline[-1]
    assert '.then(function()' in parsed.inline[-1] and '.catch(failed)' in parsed.inline[-1]
    if years != 5: assert 'fill-opacity="0.20"' in html
    assert 'id="fallback"' in html
    assert 'Sahm threshold' in html if series=='SAHMREALTIME' else True
