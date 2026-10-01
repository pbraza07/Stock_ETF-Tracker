import xml.etree.ElementTree as ET
import pytest
from recession_chart_svg import indicator_svg

@pytest.mark.parametrize('series',['USPHCI','RECPROUSM156N','SAHMREALTIME'])
def test_server_chart_has_no_script_and_keeps_shading(series):
    rows=[{'date':'2020-02-01','value':.2},{'date':'2020-03-01','value':.8},{'date':'2020-04-01','value':1.2},{'date':'2020-05-01','value':.3}]
    svg=indicator_svg(series,rows)
    root=ET.fromstring(svg)
    assert 'script' not in svg and 'iframe' not in svg
    assert 'fill-opacity="0.20"' in svg
    assert 'Observation month' in svg
    if series=='SAHMREALTIME': assert 'Sahm threshold: 0.50 pp' in svg
    assert root.tag.endswith('svg')


def test_missing_month_not_connected():
    svg=indicator_svg('USPHCI',[{'date':'2020-01-01','value':1},{'date':'2020-03-01','value':2}])
    assert svg.count('<circle ')==2

@pytest.mark.parametrize('series',['USPHCI','RECPROUSM156N','SAHMREALTIME'])
@pytest.mark.parametrize('years',[None,5,10,20])
def test_full_history_and_windows_do_not_overflow(series,years):
    import pandas as pd
    rows=[{'date':str(d.date()),'value':1.0} for d in pd.date_range('1959-01-01','2026-07-01',freq='MS')]
    svg=indicator_svg(series,rows,years)
    ET.fromstring(svg)
    assert 'Jul 2026' in svg
    if years is None: assert 'Jan 1959' in svg
