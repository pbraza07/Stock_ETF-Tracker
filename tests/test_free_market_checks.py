import json
import pytest
from free_market_checks import parse_listings,parse_quote,reserve_request,forecast_record

def test_listing_cutoff_rejects_future_delisting():
    csv='symbol,name,exchange,assetType,ipoDate,delistingDate,status\nOLD,Old,NYSE,Stock,2000-01-01,2020-01-01,Delisted\nNEW,New,NYSE,Stock,2000-01-01,2025-01-01,Delisted\n'
    assert [r['symbol'] for r in parse_listings(csv,'2021-01-01','delisted')]==['OLD']

def test_quote_identity_and_nonfinite():
    p={'Global Quote':{'01. symbol':'AAPL','05. price':'100','07. latest trading day':'2026-11-13'}}
    assert parse_quote(json.dumps(p),'AAPL')['value']==100
    with pytest.raises(ValueError):parse_quote(json.dumps(p),'MSFT')
    p['Global Quote']['05. price']='nan'
    with pytest.raises(ValueError):parse_quote(json.dumps(p),'AAPL')

def test_rolling_quota(monkeypatch,tmp_path):
    monkeypatch.delenv('MARKETSCOPE_DATABASE_URL',raising=False);monkeypatch.setenv('MARKETSCOPE_STATE_DIR',str(tmp_path))
    reserve_request(100000)
    with pytest.raises(ValueError):reserve_request(100001)
    for i in range(1,20):reserve_request(100000+i*14)
    with pytest.raises(ValueError):reserve_request(100500)
    reserve_request(200000)

def test_frozen_forecast_pending_and_dated():
    import pandas as pd
    r={'inputs':{'starting_investment':100,'future_years':1},'settings':{},'audit':{'model_version':'5.11.64','input_evidence':{'sha256':'abc'}},
       'references':{'Not Rebalanced':pd.DataFrame([{f'P{p} Ending Balance':p for p in (10,25,50,75,90)}])}}
    a=forecast_record(r)
    assert a['status'].startswith('PENDING') and a['recorded_at'] and a['sha256']

def test_no_key_no_network(monkeypatch):
    import free_market_checks as m
    monkeypatch.delenv('ALPHA_VANTAGE_API_KEY',raising=False)
    monkeypatch.setattr(m,'get',lambda k:None)
    monkeypatch.setattr(m.requests,'get',lambda *a,**k:pytest.fail('network without key'))
    with pytest.raises(ValueError,match='ALPHA_VANTAGE'):m.fetch({'symbol':'AAPL'},lambda s:s)
