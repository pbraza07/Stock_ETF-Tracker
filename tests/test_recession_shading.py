import pandas as pd
import pytest
from recession_indicators import indicator_figure, SERIES

@pytest.mark.parametrize('series', SERIES)
def test_all_graphs_show_historical_recessions(series):
    records=[{'date':str(d.date()),'value':1.0} for d in pd.date_range('1959-01-01','2026-08-01',freq='MS')]
    fig=indicator_figure(series,records,None)
    bands=[s for s in fig.layout.shapes if s.type=='rect']
    assert len(bands)==9
    assert bands[-1].x0==pd.Timestamp('2020-03-01')
    assert bands[-1].x1==pd.Timestamp('2020-04-30')
    assert all(s.layer=='below' and s.yref=='paper' for s in bands)
    assert len(fig.data[0].x)==len(records)
    if series=='SAHMREALTIME':
        assert any(s.type=='line' and s.y0==.5 for s in fig.layout.shapes)


def test_window_clipping_and_no_false_recession():
    rows=[{'date':str(d.date()),'value':80.0} for d in pd.date_range('2008-06-01','2009-02-01',freq='MS')]
    fig=indicator_figure('RECPROUSM156N',rows,None)
    assert len(fig.layout.shapes)==1
    assert fig.layout.shapes[0].x0==pd.Timestamp('2008-06-01')
    assert fig.layout.shapes[0].x1==pd.Timestamp('2009-02-01')
    rows=[{'date':'2024-01-01','value':90},{'date':'2024-02-01','value':99}]
    assert not indicator_figure('RECPROUSM156N',rows,None).layout.shapes
