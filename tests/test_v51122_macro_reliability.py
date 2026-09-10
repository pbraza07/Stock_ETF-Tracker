from datetime import datetime,timezone
import json
from unittest.mock import Mock
import requests
from macro_data import cached_download
from macro_snapshots import validate_snapshot,with_snapshot
from economic_calendar import parse_trading_economics,load_calendar
from recession_indicators import load_series
from scripts.update_macro_snapshots import save_result


def test_fred_api_uses_exact_series_and_does_not_save_key(tmp_path,monkeypatch):
    monkeypatch.setenv('FRED_API_KEY','secret-value')
    response=Mock();response.text=json.dumps({'count':2,'observations':[{'date':'2026-01-01','value':'0.3'},{'date':'2026-02-01','value':'0.5'}]})
    request=Mock(return_value=response);monkeypatch.setattr(requests,'get',request)
    result=load_series('RECPROUSM156N',True,tmp_path)
    assert result['status']=='Updated' and result['data'][-1]['value']==.5
    assert request.call_args.kwargs['params']['series_id']=='RECPROUSM156N'
    assert 'api.stlouisfed.org' in request.call_args.args[0]
    assert request.call_args.kwargs['params']['realtime_start']=='1990-07-04'
    assert request.call_args.kwargs['params']['realtime_end']=='9999-12-31'
    assert 'secret-value' not in (tmp_path/'RECPROUSM156N.json').read_text()


def test_api_error_never_discloses_key(tmp_path,monkeypatch):
    response=Mock(status_code=403)
    monkeypatch.setattr(requests,'get',Mock(side_effect=requests.HTTPError('https://api.test/?api_key=secret',response=response)))
    result=cached_download('test','https://api.test',json.loads,0,cache_dir=tmp_path,params={'api_key':'secret'})
    assert result['error']=='HTTP 403' and 'secret' not in str(result)


def test_remote_snapshot_recovers_when_provider_is_unavailable(tmp_path,monkeypatch):
    import macro_snapshots as module
    monkeypatch.setattr(module,'ROOT',tmp_path/'snapshots');monkeypatch.setattr(module,'CACHE_DIR',tmp_path/'cache')
    payload={'key':'USPHCI','data':[{'date':'2026-01-01','value':145.}], 'retrieved_at':'2026-02-01T00:00:00+00:00','source':'https://fred.stlouisfed.org/series/USPHCI'}
    response=Mock();response.json.return_value=payload;monkeypatch.setattr(requests,'get',Mock(return_value=response))
    result=with_snapshot('USPHCI',{'data':[],'status':'Unavailable','retrieved_at':None,'error':'HTTP 403'})
    assert result['status']=='Stale cache' and result['data']==payload['data']
    assert result['retrieved_at']==payload['retrieved_at'] and result['error']=='HTTP 403'


def test_failed_refresh_does_not_replace_saved_history(tmp_path):
    path=tmp_path/'USPHCI.json';path.write_text('previous good data')
    assert not save_result('USPHCI',{'status':'Stale cache','data':[]},tmp_path)
    assert path.read_text()=='previous good data'


def test_calendar_api_independent_high_importance_us_filter():
    rows=[{'CalendarId':'1','Date':'2026-09-10T12:30:00','Country':'United States','Importance':3,'Event':'CPI','Actual':'2.0%','Forecast':'2.1%','Previous':'2.2%'},
          {'Country':'Canada','Importance':3},{'Country':'United States','Importance':2}]
    events=parse_trading_economics(json.dumps(rows))
    assert len(events)==1 and events[0]['timestamp']=='2026-09-10T12:30:00+00:00'
    assert events[0]['impact']=='neutral'


def test_calendar_api_missing_key_is_actionable(monkeypatch):
    import economic_calendar as module
    monkeypatch.delenv('TRADING_ECONOMICS_API_KEY',raising=False)
    monkeypatch.setattr(module,'with_snapshot',lambda key,result:result)
    result=load_calendar('Trading Economics API')
    assert result['status']=='Unavailable' and 'not configured' in result['error']
