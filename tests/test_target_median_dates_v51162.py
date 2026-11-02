import pandas as pd
import pytest
from ranking_price_targets import enrich_targets
from test_ranking_targets_v51160 import fixtures


@pytest.mark.parametrize('placeholder',['—','',None,float('nan'),pd.NA,'None','Unavailable'])
def test_missing_quote_date_falls_back_with_an_explicit_basis(placeholder):
    table,market=fixtures();market['Data As Of']=placeholder
    market['Snapshot Updated ET']='Nov 02, 2026 02:47:58 PM EST'
    out=enrich_targets(table,market)
    assert out.iloc[0]['Price As Of']=='Snapshot refresh: Nov 02, 2026 02:47:58 PM EST'


def test_missing_snapshot_median_uses_actual_reported_median_and_recomputes_upside():
    table,market=fixtures();market=market.drop(columns='Price Target Median')
    targets={'A':dict(low=80.,median=130.,mean=135.,high=160.,retrieved_at='2026-11-02T20:00:00Z')}
    out=enrich_targets(table,market,targets)
    assert out.iloc[0]['Target Price Median']==130.
    assert out.iloc[0]['Median Target Upside %']==pytest.approx(30.)
    assert out.iloc[0]['Median Target Retrieved At']=='2026-11-02T20:00:00Z'


def test_newer_daily_snapshot_is_not_overridden_by_an_older_seed():
    table,market=fixtures();market['Price Target Updated ET']='2026-11-03T20:00:00Z'
    targets={'A':dict(low=70.,median=90.,high=100.,retrieved_at='2026-11-02T20:00:00Z')}
    assert enrich_targets(table,market,targets).iloc[0]['Target Price Median']==120.


def test_provider_continues_to_info_when_only_median_is_missing(monkeypatch):
    from providers import yahoo
    class Ticker:
        def get_analyst_price_targets(self):return dict(low=80.,mean=125.,high=160.)
        @property
        def analyst_price_targets(self):return {}
        def get_info(self):return dict(targetMedianPrice=120.)
    monkeypatch.setattr(yahoo.yf,'Ticker',lambda *a:Ticker())
    result=yahoo.YahooFinanceProvider().get_price_targets('A')
    assert result['median']==120. and result['mean']==125.


def test_unavailable_median_stays_missing_and_is_explained():
    table,market=fixtures();market=market.drop(columns='Price Target Median')
    row=enrich_targets(table,market).iloc[0]
    assert pd.isna(row['Target Price Median']) and pd.isna(row['Median Target Upside %'])
    assert 'no average substituted' in row['Target Data Status']


def test_persisted_provider_targets_are_available_before_background_fetch(monkeypatch):
    import shared_cache
    from ranking_price_targets import load_targets
    monkeypatch.setattr(shared_cache,'cached',lambda *a,**k:k['default'])
    values=load_targets(('V','SO','WMT','PG','TJX'))
    assert all(values[s].get('median')>0 for s in ('V','SO','WMT','PG','TJX'))
    assert all(values[s].get('retrieved_at') for s in values)


def test_daily_snapshot_persists_median_and_actual_quote_date(tmp_path,monkeypatch):
    from scripts import update_snapshot as update
    monkeypatch.delenv('RENDER',raising=False)
    for name in ['OUT','META_OUT','MONTHLY_OUT','MONTHLY_FULL_OUT','MONTHLY_25Y_LEGACY_OUT']:
        monkeypatch.setattr(update,name,tmp_path/(name+'.csv' if name!='META_OUT' else name+'.json'))
    monkeypatch.setattr(update,'load_default_universe',lambda:pd.DataFrame([dict(Symbol='A',Type='Stock',Name='Company A',Sector='Technology')]))
    history=pd.DataFrame({'Close':[100.,150.,200.]},index=pd.to_datetime(['2024-12-31','2025-12-31','2026-11-02']))
    monkeypatch.setattr(update,'_history_batch',lambda *a:{'A':history})
    monkeypatch.setattr(update.time,'sleep',lambda *a:None)
    class Provider:
        def get_price_targets_many(self,*a,**k):return {'A':dict(low=80.,median=120.,mean=125.,high=160.)}
    monkeypatch.setattr(update,'YahooFinanceProvider',Provider)
    update.main()
    stored=pd.read_csv(update.OUT)
    assert stored.iloc[0]['Price Target Median']==120.
    assert stored.iloc[0]['Price Target Average']==125.
    assert stored.iloc[0]['Data As Of']=='2026-11-02'
    ranking=pd.DataFrame([dict(Symbol='A',Rank=1,Price=180.)])
    shown=enrich_targets(ranking,stored)
    assert shown.iloc[0]['Target Price Median']==120.
    assert shown.iloc[0]['Median Target Upside %']==pytest.approx(-40.)
    assert shown.iloc[0]['Price As Of']=='2026-11-02'


def test_eastern_source_times_are_compared_in_the_correct_timezone():
    table,market=fixtures()
    market['Price Target Updated ET']='Nov 02, 2026 04:00:00 PM EST'
    targets={'A':dict(low=70.,median=90.,high=100.,retrieved_at='2026-11-02T20:00:00Z')}
    assert enrich_targets(table,market,targets).iloc[0]['Target Price Median']==120.
