import numpy as np
import pandas as pd
import pytest
from quality_opportunities import controls,quality_table,screen,portfolio,path_metrics,MODES
from test_v510_future_projection import market_fixture,monthly_fixture as base_monthly,YEARS

def monthly_fixture(months):
    value=base_monthly(months)
    value['returns']['EEE']=dict(value['returns']['AAA'])
    return value

def fixture():
    market=market_fixture();market['Price']=100.;market['MarketCap']=1e11
    fund={s:dict(forward_pe=20,earnings_growth=.15,revenue_growth=.12,operating_margin=.2,
        return_on_equity=.2,debt_to_equity=30,free_cash_flow=6e9,market_cap=1e11) for s in market.Symbol}
    return market,{'fundamentals':fund,'macro':{'treasury_10y':{'value':4,'observation_date':'2025-12-01'}}}

def permissive():return dict(count=100,min_quality=0,min_probability=0,max_loss_probability=.99,max_severe_probability=.99,max_tail_loss=.99)

def test_all_stocks_and_no_etfs_evaluated_reproducibly():
    market,context=fixture()
    a=screen(market,YEARS,monthly_fixture(24),context,permissive())
    b=screen(market,YEARS,monthly_fixture(24),context,permissive())
    assert a['universe_count']==4 and len(a['table'])==4
    assert 'CCC' not in a['table'].Ticker.tolist()
    pd.testing.assert_frame_equal(a['table'],b['table'])
    assert (a['table']['Probability status']=='UNCALIBRATED MODEL ESTIMATE').all()

def test_missing_fundamentals_never_rewarded_or_filled():
    market,context=fixture();context['fundamentals']['AAA']={}
    q=quality_table(market,context).set_index('Ticker')
    assert q.loc['AAA','Quality score']==0
    r=screen(market,YEARS,monthly_fixture(24),context,permissive())
    assert 'AAA' in r['excluded'].Ticker.tolist()

def test_weak_profitability_not_rescued_by_sector_percentiles():
    m,c=fixture();c['fundamentals']['AAA']['operating_margin']=-.02
    r=screen(m,YEARS,monthly_fixture(24),c,permissive())
    assert 'AAA' in r['excluded'].Ticker.tolist()

def test_historical_winner_does_not_raise_forward_drift():
    m,c=fixture();a=screen(m,YEARS,monthly_fixture(24),c,permissive())
    m.loc[m.Symbol.eq('AAA'),YEARS]=100.
    b=screen(m,YEARS,monthly_fixture(24),c,permissive())
    assert a['table'].set_index('Ticker').loc['AAA','Expected Investment Return']==b['table'].set_index('Ticker').loc['AAA','Expected Investment Return']

def test_no_qualifiers_when_threshold_not_met():
    market,context=fixture()
    r=screen(market,YEARS,monthly_fixture(24),context,dict(permissive(),min_probability=.99,target=2.))
    assert r['leaders'].empty and len(r['table'])==4

def test_annualized_is_not_every_year():
    returns=np.zeros((24,100,1));returns[11]=.50;returns[23]=-.10
    base=dict(controls(),years=2,annual_fee=0,trade_cost=0,target=.15)
    a=path_metrics(returns,np.zeros(100),dict(base,mode=MODES[1]))
    b=path_metrics(returns,np.zeros(100),dict(base,mode=MODES[2]))
    assert a['Target probability']==1 and b['Target probability']==0
    assert a['Median return']==pytest.approx(np.sqrt(1.35)-1)

def test_costs_reduce_returns_and_joint_portfolio_not_probability_average():
    r=np.zeros((12,100,2));r[0,:50]=[.6,-.6];r[0,50:]=[-.6,.6]
    cfg=dict(controls(),annual_fee=0,trade_cost=0)
    joint=path_metrics(r,np.zeros(100),cfg)
    single=path_metrics(r[:,:,:1],np.zeros(100),cfg)
    assert joint['Target probability']==0 and single['Target probability']==.5
    costs=path_metrics(r,np.zeros(100),dict(cfg,trade_cost=.01,annual_fee=.01))
    assert costs['Median return']<joint['Median return']

def test_portfolio_enforces_sector_limit_and_produces_both_strategies():
    market,context=fixture();r=screen(market,YEARS,monthly_fixture(24),context,permissive())
    selected=['AAA','BBB','DDD','EEE']
    with pytest.raises(ValueError,match='sector limits'):portfolio(market,YEARS,monthly_fixture(24),context,selected,r)
    p=portfolio(market,YEARS,monthly_fixture(24),context,selected,r,max_sector=.5)
    assert set(p['metrics'])=={'Rebalanced (yearly)','Non-Rebalanced'}
    assert p['sector_allocation']['Technology']==.5

def test_future_information_cannot_enter_cutoff_inputs():
    from opportunity_walk_forward import inputs_at
    records=[dict(kind='universe',key='AAA',value={'eligible':True,'sector':'Technology','price':100},available_at='2020-01-01',observation_date='2020-01-01'),
        dict(kind='fundamentals',key='AAA',value={'forward_pe':999},available_at='2022-01-01',observation_date='2020-01-01')]
    _,_,_,context=inputs_at(records,'2020-12-31')
    assert context['fundamentals']=={}

def test_ui_initial_view_has_targets_without_automatic_requests():
    from streamlit.testing.v1 import AppTest
    app=AppTest.from_string('''
from quality_opportunities_ui import render
from test_quality_opportunities import fixture
def never(*a):raise AssertionError('unexpected automatic request')
render(fixture()[0],['2025'],never,never)
''').run(timeout=15)
    assert not app.exception
    assert any('Target return' in x.label for x in app.number_input)

def test_completed_screen_ui_and_audit_are_renderable():
    from streamlit.testing.v1 import AppTest
    app=AppTest.from_string('''
import streamlit as st
from quality_opportunities_ui import render
from quality_opportunities import screen
from test_quality_opportunities import fixture,monthly_fixture,permissive,YEARS
m,c=fixture();monthly=monthly_fixture(24)
st.session_state.qo_bundle=dict(result=screen(m,YEARS,monthly,c,permissive()),market=m,context=c,monthly=monthly,years=YEARS)
render(m,YEARS,lambda *a: monthly,lambda *a:c)
''').run(timeout=15)
    assert not app.exception
    assert len(app.dataframe)>=2

def test_paper_records_append_without_replacing(tmp_path,monkeypatch):
    from opportunity_paper import save_record
    monkeypatch.delenv('MARKETSCOPE_GITHUB_TOKEN',raising=False)
    a,ok,_=save_record({'test':1},tmp_path);b,_,_=save_record({'test':2},tmp_path)
    assert a!=b and not ok and len(list(tmp_path.glob('*.json')))==2

def test_walk_forward_executes_same_screen_and_keeps_future_outcomes_separate():
    from opportunity_walk_forward import run_bundle
    m,c=fixture();monthly=monthly_fixture(24);records=[]
    def add(kind,key,value,stamp):records.append(dict(kind=kind,key=key,value=value,available_at=stamp,observation_date=stamp))
    for _,row in m[m.Type.eq('Stock')].iterrows():
        s=row.Symbol
        add('universe',s,dict(eligible=True,sector=row.Sector,price=100,market_cap=1e11),'2025-12-01')
        add('fundamentals',s,c['fundamentals'][s],'2025-12-01')
        for year in YEARS:add('prices',s,row[year]/100,year+'-12-31')
        for period,value in monthly['returns'][s].items():add('monthly',s,value,str(pd.Period(period).end_time.date()))
    add('macro','treasury_10y',4.,'2025-12-01')
    report=run_bundle(dict(records=records,cutoffs=['2025-12-31'],screen_settings=permissive(),
        realized_annual_returns={s:{'2026':.3} for s in m.Symbol},sp500_annual_returns={'2026':.1}))
    assert len(report['records'])==4 and report['independent_calendar_windows']==1
    assert all(x['target_hit'] for x in report['records'])
    assert report['confidence'].startswith('UNVALIDATED')

def test_background_screen_completes_and_hands_off_to_ui():
    from streamlit.testing.v1 import AppTest
    from projection_jobs import poll
    app=AppTest.from_string('''
from quality_opportunities_ui import render
from test_quality_opportunities import fixture,monthly_fixture,YEARS
m,c=fixture()
render(m,YEARS,lambda *a:monthly_fixture(24),lambda *a:c)
''').run(timeout=15)
    button=next(x for x in app.button if x.label=='Evaluate current stock universe')
    button.click().run(timeout=15)
    token=app.session_state.qo_job
    poll(token)['future'].result(timeout=20)
    app.run(timeout=15)
    assert not app.exception
    assert app.session_state.qo_bundle['result']['universe_count']==4
    assert poll(token) is None
