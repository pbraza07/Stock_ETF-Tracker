import json
import requests
import macro_data
from projection_macro import fetch_one, freshness, observations

def test_api_and_last_successful_cache(monkeypatch,tmp_path):
    monkeypatch.setenv('FRED_API_KEY','test-secret-not-real')
    calls=[]
    class Response:
        text=json.dumps({'observations':[{'date':'2026-08-01','value':'4.2'},{'date':'2026-07-01','value':'4.1'}]})
        def raise_for_status(self): pass
    def get(url,**kwargs): calls.append((url,kwargs));return Response()
    monkeypatch.setattr(macro_data.requests,'get',get)
    _,first=fetch_one('rate','FEDFUNDS',cache_dir=tmp_path)
    assert first['value']==4.2 and first['status']=='Updated'
    assert calls[0][1]['params']['api_key']=='test-secret-not-real'
    def fail(*a,**kw): raise requests.Timeout('secret-url-must-not-leak')
    monkeypatch.setattr(macro_data.requests,'get',fail)
    _,stale=fetch_one('rate','FEDFUNDS',cache_dir=tmp_path,force=True)
    assert stale['status']=='Stale cache' and stale['observations']==first['observations']
    assert stale['retrieved_at']==first['retrieved_at']
    assert 'secret-url' not in str(stale)

def test_statuses():
    expected={'a':'A','b':'B'}
    row={'value':1.,'observation_date':'2026-08-01','status':'Updated'}
    assert freshness({},expected)['status']=='UNAVAILABLE'
    assert freshness({'a':row},expected)['status']=='PARTIAL'
    assert freshness({'a':row,'b':row},expected)['status']=='AVAILABLE'
    assert freshness({'a':row,'b':{**row,'status':'Stale cache'}},expected)['status']=='STALE'

def test_csv_without_key(monkeypatch,tmp_path):
    monkeypatch.delenv('FRED_API_KEY',raising=False)
    class Response:
        text='observation_date,FEDFUNDS\n2026-08-01,4.2\n'
        def raise_for_status(self): pass
    monkeypatch.setattr(macro_data.requests,'get',lambda *a,**kw:Response())
    assert fetch_one('rate','FEDFUNDS',cache_dir=tmp_path)[1]['value']==4.2
