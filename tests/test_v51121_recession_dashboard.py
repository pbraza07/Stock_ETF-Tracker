from datetime import datetime
from pathlib import Path
from unittest.mock import Mock
from zoneinfo import ZoneInfo
import requests
import pytest
from economic_calendar import parse_calendar,week_events,calendar_table
from recession_indicators import parse_fred,indicator_figure,load_series
from macro_data import cached_download


def row(country='United States',stars=3,timestamp='2026-09-10 12:30:00',name='Initial Jobless Claims'):
    return f'''<tr id="eventRowId_1" event_timestamp="{timestamp}"><td class="time">08:30</td><td class="flagCur"><span title="{country}">USD</span></td><td class="sentiment">{('<i class="grayFullBullishIcon"></i>'*stars)}</td><td class="event">{name}</td><td class="act redFont">206K</td><td class="fore">205K</td><td class="prev">207K</td></tr>'''


def parse(fragment):return parse_calendar('<table class="ecoCalTable">'+fragment+'</table>')


def test_calendar_strict_filters_timezone_and_escaping():
    events=parse(row()+row('United Kingdom')+row(stars=2))
    assert len(events)==1 and events[0]['importance']==3
    html=calendar_table(events)
    assert '08:30 AM EDT' in html and '206K' in html and 'negative' in html
    assert '<iframe' not in html and 'sslecal2' not in html
    events[0]['event']='<script>bad()</script>'
    assert '<script>' not in calendar_table(events)
    winter=parse(row(timestamp='2026-01-09 13:30:00'))
    assert '08:30 AM EST' in calendar_table(winter)


def test_week_rollover_never_displays_previous_week_as_current():
    events=parse(row(timestamp='2026-09-07 01:00:00')) # Sunday evening ET
    now=datetime(2026,9,10,tzinfo=ZoneInfo('America/New_York'))
    assert week_events(events,now)[0]==[]
    with pytest.raises(ValueError):parse_calendar('<html>Access denied</html>')


def test_fred_parsing_and_threshold_in_correct_units():
    rows=parse_fred('observation_date,RECPROUSM156N\n2026-01-01,0.49\n2026-02-01,.\n2026-03-01,0.50\n','RECPROUSM156N')
    assert len(rows)==2 and rows[-1]['value']==.5
    figure=indicator_figure('RECPROUSM156N',rows).to_dict()
    assert not figure['layout'].get('shapes')
    assert figure['layout']['yaxis']['range']==[0,100]
    assert figure['layout']['yaxis']['title']['text']=='Percent'
    with pytest.raises(ValueError):parse_fred('<html>Bad</html>','USPHCI')


def test_last_valid_cache_survives_outage_without_becoming_fresh(tmp_path,monkeypatch):
    response=Mock();response.text='valid'
    monkeypatch.setattr(requests,'get',Mock(return_value=response))
    first=cached_download('test','https://example.test',lambda text:[{'value':1}],0,cache_dir=tmp_path)
    monkeypatch.setattr(requests,'get',Mock(side_effect=requests.Timeout('offline')))
    fallback=cached_download('test','https://example.test',lambda text:[],0,cache_dir=tmp_path)
    assert fallback['status']=='Stale cache' and fallback['retrieved_at']==first['retrieved_at']
    assert fallback['data']==first['data']
    empty=cached_download('missing','https://example.test',lambda text:[],0,cache_dir=tmp_path)
    assert empty['status']=='Unavailable' and empty['data']==[]


def test_recession_tab_renders_both_native_charts(monkeypatch):
    import recession_indicators as module
    from streamlit.testing.v1 import AppTest
    def fake(series,force=False):
        return {'data':[{'date':'2026-01-01','value':.3 if series=='RECPROUSM156N' else 100},{'date':'2026-02-01','value':.5 if series=='RECPROUSM156N' else 101}], 'status':'Updated','retrieved_at':'2026-03-01T00:00:00+00:00'}
    monkeypatch.setattr(module,'load_series',fake)
    app=AppTest.from_string('from recession_indicators import render_recession_indicators\nrender_recession_indicators()').run()
    assert not app.exception
    assert len(app.get('plotly_chart'))==2
    assert any(metric.value=='Smoothed probability' for metric in app.metric)
    app.selectbox[0].select('All history').run()
    assert not app.exception and len(app.get('plotly_chart'))==2


def test_calendar_native_ui(monkeypatch):
    import economic_calendar as module
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr(module,'cached_download',lambda *a,**k:{'data':parse(row()),'status':'Updated','retrieved_at':'2026-09-10T12:00:00+00:00'})
    app=AppTest.from_string('from economic_calendar import render_economic_calendar\nrender_economic_calendar()').run()
    assert not app.exception
    assert any('ms-economic' in item.value for item in app.markdown)
    assert not app.get('iframe')
