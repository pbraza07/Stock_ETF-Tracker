import json
from unittest.mock import Mock
import requests
from recession_indicators import indicator_figure,load_series


def test_sahm_threshold_is_percentage_points_not_probability():
    fig=indicator_figure('SAHMREALTIME',[{'date':'2026-01-01','value':-.1},{'date':'2026-02-01','value':.5}]).to_dict()
    assert fig['layout']['shapes'][0]['y0']==.5
    assert fig['layout']['yaxis']['title']['text']=='Percentage points'
    assert 'range' not in fig['layout']['yaxis']
    assert ' pp' in fig['data'][0]['hovertemplate']


def test_sahm_api_uses_requested_vintage_window(monkeypatch,tmp_path):
    monkeypatch.setenv('FRED_API_KEY','test-secret')
    response=Mock();response.text=json.dumps({'observations':[{'date':'2026-01-01','value':'-.1'}]})
    get=Mock(return_value=response);monkeypatch.setattr(requests,'get',get)
    result=load_series('SAHMREALTIME',True,tmp_path)
    assert result['data'][0]['value']==-.1
    assert get.call_args.kwargs['params']['series_id']=='SAHMREALTIME'
    assert get.call_args.kwargs['params']['realtime_start']=='1990-07-04'
    assert get.call_args.kwargs['params']['realtime_end']=='9999-12-31'
