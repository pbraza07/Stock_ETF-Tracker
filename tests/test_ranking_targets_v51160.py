import pandas as pd
import numpy as np
import pytest
from ranking_price_targets import enrich_targets,TARGET_COLUMNS
from top12_ui import _persisted_display_table


def fixtures():
    table=pd.DataFrame([dict(Rank=1,Symbol='A',Name='Company A',Sector='Tech',Price=90.,**{'Max Profit Score':80.,'Recession Score':70.})])
    market=pd.DataFrame([dict(Symbol='A',Price=100.,**{'Price Target Low':80.,'Price Target Median':120.,'Price Target Average':125.,'Price Target High':160.,'Price Target Updated ET':'2026-11-01','Data As Of':'2026-11-02'})])
    return table,market


@pytest.mark.parametrize('kind',['Recession','Max Profit'])
def test_both_saved_rankings_show_exact_target_comparisons_without_changing_rank(kind):
    table,market=fixtures();out=_persisted_display_table(table,kind,market)
    assert set(TARGET_COLUMNS)<=set(out)
    assert out.iloc[0]['Target Price Median']==120.
    assert out.iloc[0]['Median Target Upside %']==pytest.approx(20.)
    assert out.iloc[0]['Current Price Minus Low Target']==20.
    assert out.iloc[0]['Current Price']==100.
    assert out.iloc[0]['Rank']==1
    assert table.iloc[0].Price==90.


def test_mean_is_never_substituted_for_median_or_zero():
    table,market=fixtures();market=market.drop(columns='Price Target Median')
    out=enrich_targets(table,market)
    assert pd.isna(out.iloc[0]['Target Price Median'])
    assert pd.isna(out.iloc[0]['Median Target Upside %'])
    assert out.iloc[0]['Current Price Minus Low Target']==20.


def test_fresh_partial_provider_snapshot_not_spliced_with_older_targets():
    table,market=fixtures()
    out=enrich_targets(table,market,{'A':{'low':110.,'median':None,'high':None,'retrieved_at':'2026-11-02','source':'Provider'}})
    assert pd.isna(out.iloc[0]['Target Price Median'])
    assert pd.isna(out.iloc[0]['Target Price High'])
    assert out.iloc[0]['Current Price Minus Low Target']==-10.
    assert out.iloc[0]['Target Source']=='Provider'


def test_missing_zero_or_nonfinite_quotes_never_divide_by_zero():
    table,market=fixtures();table['Price']=np.nan
    for value in [0.,-1.,np.inf,np.nan,None]:
        market['Price']=value
        out=enrich_targets(table,market)
        assert pd.isna(out.iloc[0]['Median Target Upside %'])
        assert pd.isna(out.iloc[0]['Current Price Minus Low Target'])


def test_missing_source_and_old_ranking_compatible():
    table,_=fixtures();out=enrich_targets(table)
    assert out['Target Price Median'].isna().all()
    assert out['Rank'].tolist()==table['Rank'].tolist()


def test_reports_include_target_evidence():
    from io import BytesIO
    from pypdf import PdfReader
    from top12_exports import build_top12_pdf,build_top12_excel
    from test_v5115_top12 import fixture,YEARS
    from top12_rankings import build_top12_rankings
    result=build_top12_rankings(fixture(),YEARS,simulations=100)
    table=result['Max Profit'].head(1)
    targets={table.iloc[0].Symbol:dict(low=100.,median=120.,high=150.,retrieved_at='2026-11-02',source='Test source')}
    enriched=enrich_targets(table,targets=targets)
    excel=build_top12_excel('Max Profit',enriched,result)
    sheet=pd.read_excel(BytesIO(excel),sheet_name='Top 5 per Sector')
    assert sheet.iloc[0]['Target Price Median']==120.
    pdf=build_top12_pdf('Max Profit',enriched,result)
    text='\n'.join(p.extract_text() for p in PdfReader(BytesIO(pdf)).pages)
    assert 'Target Price Median' in text and 'Median Target Upside' in text


def test_target_cache_failures_cannot_hide_saved_ranking(monkeypatch):
    import shared_cache
    from ranking_price_targets import load_targets
    def unavailable(*a,**k):raise RuntimeError('cache unavailable')
    monkeypatch.setattr(shared_cache,'cached',unavailable)
    assert load_targets(('A',))=={}


def test_target_requests_are_background_and_batched(monkeypatch):
    import shared_cache
    from ranking_price_targets import load_targets
    calls=[]
    def cache(namespace,inputs,loader,**kwargs):
        calls.append((namespace,inputs,kwargs))
        return {'A':{'median':120.}}
    monkeypatch.setattr(shared_cache,'cached',cache)
    assert load_targets(('B','A','A'))['A']['median']==120.
    assert calls[0][1]==('A','B') and calls[0][2]['background']
