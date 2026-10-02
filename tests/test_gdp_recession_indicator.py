from datetime import datetime,timezone
import pytest
from recession_indicators import parse_fred,indicator_figure
from recession_chart_svg import indicator_svg
from macro_snapshots import validate_snapshot

ROWS=[{'date':'2007-10-01','value':20},{'date':'2008-01-01','value':70},
      {'date':'2008-04-01','value':90},{'date':'2008-07-01','value':80}]

def test_quarters_remain_connected_with_thresholds_and_recession_shading():
    fig=indicator_figure('JHGDPBRINDX',ROWS,None)
    assert len(fig.data[0].y)==4
    assert list(fig.data[0].y)==[20,70,90,80]
    assert list(fig.layout.yaxis.range)==[0,100]
    assert {s.y0 for s in fig.layout.shapes if s.type=='line'}=={33,67}
    assert any(s.type=='rect' for s in fig.layout.shapes)
    svg=indicator_svg('JHGDPBRINDX',ROWS,None)
    assert 'Entry threshold: above 67%' in svg and 'Exit threshold: below 33%' in svg
    assert 'Observation quarter' in svg and 'stroke="#34D399" stroke-width="2.5"' in svg

def test_missing_quarter_is_not_filled():
    fig=indicator_figure('JHGDPBRINDX',[ROWS[0],ROWS[2]],None)
    import pandas as pd
    assert pd.isna(fig.data[0].y[1])
    assert fig.data[0].connectgaps is False

def test_gdp_parser_and_snapshot_probability_bounds():
    assert parse_fred('DATE,JHGDPBRINDX\n2026-01-01,7.0','JHGDPBRINDX')[0]['value']==7
    with pytest.raises(ValueError):parse_fred('DATE,JHGDPBRINDX\n2026-01-01,101','JHGDPBRINDX')
    snapshot={'key':'JHGDPBRINDX','data':ROWS,'retrieved_at':datetime.now(timezone.utc).isoformat()}
    assert validate_snapshot(snapshot,'JHGDPBRINDX')['data']==ROWS

def test_gdp_interactive_has_same_chart_and_no_external_scripts():
    from recession_interactive import interactive_html
    html=interactive_html('JHGDPBRINDX',ROWS,None)
    assert 'GDP-Based Recession Indicator Index' in html
    assert 'Entry threshold: above 67%' in html
    assert '<script src=' not in html
