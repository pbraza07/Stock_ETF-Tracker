import json
from unittest.mock import Mock
import requests
from macro_data import cached_download
from recession_indicators import load_series


def test_timeout_retries_then_saves_valid_response(tmp_path,monkeypatch):
    response=Mock(text='{"valid":true}')
    request=Mock(side_effect=[requests.ReadTimeout('secret'),response])
    monkeypatch.setattr(requests,'get',request)
    result=cached_download('test','https://example.test',json.loads,0,True,tmp_path,attempts=2,timeout=(5,30))
    assert result['status']=='Updated' and request.call_count==2
    assert request.call_args.kwargs['timeout']==(5,30)


def test_api_timeout_falls_back_to_official_csv(tmp_path,monkeypatch):
    monkeypatch.setenv('FRED_API_KEY','private-test-key')
    response=Mock(text='observation_date,USPHCI\n2026-01-01,150\n')
    request=Mock(side_effect=[requests.ReadTimeout('private-test-key'),response])
    monkeypatch.setattr(requests,'get',request)
    result=load_series('USPHCI',True,tmp_path)
    assert result['status']=='Updated' and result['data'][0]['value']==150
    assert 'fredgraph.csv' in result['source']
    assert 'private-test-key' not in str(result)


def test_background_uses_longer_retries_and_preserves_last_good(tmp_path,monkeypatch):
    monkeypatch.delenv('FRED_API_KEY',raising=False)
    original={'retrieved_at':'2026-01-01T00:00:00+00:00','source':'https://fred.test','data':[{'date':'2025-12-01','value':10}]}
    path=tmp_path/'USPHCI.json';path.write_text(json.dumps(original))
    request=Mock(side_effect=requests.ReadTimeout('secret url'))
    monkeypatch.setattr(requests,'get',request)
    result=load_series('USPHCI',True,tmp_path,background=True)
    assert result['status']=='Stale cache' and result['retrieved_at']==original['retrieved_at']
    assert request.call_count==2 and request.call_args.kwargs['timeout']==(5,30)
    assert json.loads(path.read_text())==original


def test_auth_failure_not_retried(tmp_path,monkeypatch):
    response=Mock(status_code=401)
    request=Mock(side_effect=requests.HTTPError('secret',response=response))
    monkeypatch.setattr(requests,'get',request)
    result=cached_download('test','https://example.test',json.loads,0,True,tmp_path,attempts=2)
    assert request.call_count==1 and result['error']=='HTTP 401'


def test_collector_isolates_failure_and_reports_each_series(tmp_path,monkeypatch):
    from scripts import update_macro_snapshots as module
    def load(key,force,background=False):
        assert force and background
        if key=='USPHCI': raise ValueError('must not print secret')
        return {'status':'Updated','data':[]}
    saved=[]
    monkeypatch.setattr(module,'load_series',load)
    monkeypatch.setattr(module,'save_result',lambda key,result: saved.append(key) or True)
    summary=tmp_path/'summary.md';monkeypatch.setenv('GITHUB_STEP_SUMMARY',str(summary))
    assert module.main()==1
    assert set(saved)=={'RECPROUSM156N','SAHMREALTIME'}
    assert 'USPHCI | Failed' in summary.read_text()
    assert 'secret' not in summary.read_text()
