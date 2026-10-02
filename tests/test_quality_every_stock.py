from datetime import datetime,timezone,timedelta
import pandas as pd
from quality_opportunities import screen
from opportunity_results import result_table
from opportunity_data import retain_observed_fundamentals
from test_quality_opportunities import fixture,monthly_fixture,permissive,YEARS

def test_missing_all_fundamentals_still_generates_risk_estimates_for_every_stock():
    m,c=fixture();c['fundamentals']={}
    r=screen(m,YEARS,monthly_fixture(24),c,permissive())
    out=result_table(r,m,c)
    assert len(out)==4 and out['Quality score'].eq(0).all()
    assert out['Forecast available'].all() and out['Target probability'].notna().all()
    assert out['Criteria assessed'].eq(4).all()
    assert not out.Qualifies.any()
    assert out.Status.eq('EVALUATED — LIMITED DATA').all()

def test_no_macro_or_history_returns_quality_evaluation_without_fake_probabilities():
    m,c=fixture();c['macro']={}
    r=screen(m,YEARS,{},c,permissive())
    out=result_table(r,m,c)
    assert len(out)==4 and out['Quality score'].notna().all()
    assert out['Criteria assessed'].eq(1).all()
    assert out['Target probability'].isna().all()
    assert not out.Qualifies.any()
    assert out.Notes.str.contains('Forward CMA unavailable').all()

def test_missing_history_preserves_all_rows():
    m,c=fixture()
    r=screen(m,YEARS,{},c,permissive())
    assert len(r['table'])==4
    assert not r['table']['Forecast available'].any()

def test_cache_recovers_only_observed_recent_fields_and_keeps_their_dates(tmp_path):
    p=tmp_path/'cache.json';now=datetime.now(timezone.utc)
    original=(now-timedelta(days=2)).isoformat()
    retain_observed_fundamentals({'fundamentals':{'AAA':{'return_on_equity':.2,'retrieved_at':original}}},p,now)
    c=retain_observed_fundamentals({'fundamentals':{},'requested_symbols':['AAA']},p,now)
    assert c['fundamentals']['AAA']['return_on_equity']==.2
    assert c['fundamentals']['AAA']['cached_fields']['return_on_equity']==original
    assert 'operating_margin' not in c['fundamentals']['AAA']
    c=retain_observed_fundamentals({'fundamentals':{},'requested_symbols':['AAA']},p,now+timedelta(days=8))
    assert 'return_on_equity' not in c['fundamentals']['AAA']

def test_legacy_saved_run_is_evaluated_from_available_quality_evidence():
    m,c=fixture()
    r={'table':pd.DataFrame(),'excluded':pd.DataFrame([{'Ticker':'AAA','Reason':'Previous run skipped insufficient fundamentals'}]),'settings':permissive()}
    from quality_opportunities import controls
    r['settings']=controls(r['settings'])
    out=result_table(r,m,c)
    assert len(out)==4 and out['Quality score'].notna().all()
    assert out['Criteria assessed'].eq(1).all()
    assert not out.Status.str.contains('NOT SCORED').any()
