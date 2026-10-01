import json
from unittest.mock import Mock
import requests
import pytest
from recession_indicators import load_series,parse_fred,SERIES


def test_latest_vintage_used_independently_of_response_order(monkeypatch,tmp_path):
    monkeypatch.setenv('FRED_API_KEY','test-key')
    response=Mock();response.text=json.dumps({'count':2,'observations':[
        {'date':'2026-01-01','value':'0.76','realtime_start':'2026-09-01'},
        {'date':'2026-01-01','value':'0.9','realtime_start':'2026-02-01'}]})
    monkeypatch.setattr(requests,'get',Mock(return_value=response))
    result=load_series('RECPROUSM156N',True,tmp_path)
    assert result['data']==[{'date':'2026-01-01','value':.76}]
    assert list(SERIES)==['USPHCI','RECPROUSM156N','SAHMREALTIME']


def test_probability_units_are_not_rescaled_and_invalid_values_rejected():
    assert parse_fred('DATE,RECPROUSM156N\n2026-01-01,0.76','RECPROUSM156N')[0]['value']==.76
    with pytest.raises(ValueError):parse_fred('DATE,RECPROUSM156N\n2026-01-01,101','RECPROUSM156N')
