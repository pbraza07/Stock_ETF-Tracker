from unittest.mock import patch
import numpy as np
import pandas as pd
import pytest
from providers.yahoo import YahooFinanceProvider
from planning_assumptions import settings,decomposition,forward_cma
from planning_cashflows import simulate,sustainable_withdrawal
from planning_validation import freeze_snapshot,calibration
from ytd_simulator import simulate_ytd
from test_forward_planning import inputs,config

class Analyst:
    def get_info(self):return {'quoteType':'EQUITY','currentPrice':100}
    def get_eps_revisions(self):return pd.DataFrame({'upLast30days':[0],'downLast30days':[10],'downLast7days':[5]},index=['+1y'])
    def get_growth_estimates(self):return pd.DataFrame({'stock':[.5,.6],'industry':[.04,.04],'sector':[.05,.05],'index':[.06,.06]},index=['0q','+1y'])
    def get_analyst_price_targets(self):return {'mean':200}

def fundamentals(cls=Analyst):
    with patch('providers.yahoo.yf.Ticker',return_value=cls()):
        return YahooFinanceProvider.get_projection_fundamentals.__wrapped__(YahooFinanceProvider(),'TEST')

def test_revision_sign_and_company_horizon():
    f=fundamentals()
    assert f['eps_revision_direction']==-1
    assert f['forward_eps_growth']==.6
    assert f['eps_revision_period']=='+1y'
    assert f['analyst_target_upside_signal']>0

def test_missing_revision_never_target_upside():
    class Missing(Analyst):
        def get_eps_revisions(self):return pd.DataFrame()
        def get_growth_estimates(self):return pd.DataFrame({'industry':[.4]},index=['+1y'])
    f=fundamentals(Missing)
    assert f['eps_revision_direction'] is None and f['forward_eps_growth'] is None

def test_zero_and_missing_quality_are_distinct():
    calc=lambda v:decomposition('X','Technology',{'return_on_equity':v},.06,1,settings())['Quality / ROIC proxy']
    assert calc(0)<calc(.1)==calc(None)

def test_missing_exchange_days_rejected_holiday_allowed():
    with pytest.raises(ValueError,match='trading sessions'):
        simulate_ytd(pd.DataFrame({'A':[100,110]},index=pd.to_datetime(['2026-01-02','2026-01-09'])),100,as_of='2026-01-09')
    _,daily=simulate_ytd(pd.DataFrame({'A':[100,110]},index=pd.to_datetime(['2025-12-31','2026-01-02'])),100,as_of='2026-01-02')
    assert len(daily)==1

def test_failed_slot_is_not_rebought():
    i=inputs();i.update(holdings=['A','B'],allocations={'A':50,'B':50},withdrawal_frequency='No Withdrawal',rebalancing_frequency='Monthly')
    r=np.zeros((24,1,2));r[0,0,0]=-.9;r[1:,0,1]=.01
    c=config(expense_ratio=0,trading_friction=0,bid_ask=0)
    result=simulate(r,i,c,'Rebalanced',impairment_month=np.array([[0,24]]))
    assert result['final_holdings'][0,0]==pytest.approx(5000)
    assert result['final_holdings'][0,1]>50000

def test_contribution_cadence_independent_of_spending():
    i=inputs();i.update(additional_contribution=100,annual_withdrawal=0,monthly_withdrawal=0)
    r=np.zeros((24,1,len(i['holdings'])))
    c=config(contribution_frequency='Yearly',expense_ratio=0,trading_friction=0,bid_ask=0)
    a=simulate(r,i,c,'Non-Rebalanced')['ending']
    b=simulate(r,dict(i,withdrawal_frequency='Monthly'),c,'Non-Rebalanced')['ending']
    assert np.array_equal(a,b) and a[0]==100200

def test_timestamp_aware_cutoff():
    rows=[dict(kind='macro',key='gdp',observation_date='2020-01-01',available_at='2020-02-01T00:00:00Z',value=1),dict(kind='macro',key='gdp',observation_date='2020-01-01',available_at='2021-01-01T00:00:00Z',value=9)]
    assert [r['value'] for r in freeze_snapshot(rows,'2020-03-01')]==[1]

def test_cma_effective_weights_and_dependency_disclosure():
    c=forward_cma({},config())
    assert sum(row['Effective weight'] for row in c['components'])==pytest.approx(1)
    assert 'not independent' in c['component_dependence']
    assert c['confidence']=='LOW'

def test_cross_source_matching_requires_same_basis():
    from investment_evidence import compare_reported_prices
    a=dict(value=100,source='A',currency='USD',observation_date='2026-01-02',price_basis='unadjusted')
    assert compare_reported_prices(a,dict(a,source='B',value=100.1))['status']=='MATCH'
    assert compare_reported_prices(a,dict(a,source='B',currency='EUR'))['status']=='NOT COMPARABLE'

def test_solver_uses_disjoint_holdout_and_lower_bound():
    i=inputs();n=len(i['holdings']);r=np.zeros((24,400,n))
    out=sustainable_withdrawal({'returns':r,'inflation':np.zeros((24,400)),'rates':np.zeros((24,400))},i,config(inflation=0,expense_ratio=0,trading_friction=0,bid_ask=0),'Non-Rebalanced')
    assert out['paths']==out['holdout_paths']==200
    assert out['holdout_sampling_lower_95']<out['achieved_sample_probability']
    assert out['initial_annual_withdrawal']>49000


def test_observed_stress_requires_complete_windows():
    from types import SimpleNamespace
    from planning_engine import historical_stress_tests
    model=SimpleNamespace(symbols=['A'],historical_returns=pd.DataFrame({'Ticker':['A']*12,'Period':pd.period_range('2022-01',periods=12,freq='M').astype(str),'Return':[.01]*12,'Frequency':['Monthly']*12,'Data Status':['Observed']*12}))
    i=inputs();i.update(holdings=['A'],allocations={'A':100},withdrawal_frequency='No Withdrawal')
    rows,gaps=historical_stress_tests(model,i,config(expense_ratio=0),'Non-Rebalanced')
    assert len(rows)==1 and 'Observed replay' in rows[0]['Stress']
    assert rows[0]['Ending value']==pytest.approx(100000*1.01**12)
    assert len(gaps)==3


def test_wrong_version_cannot_certify_probability_records():
    rows=[{'Cutoff':f'{year}-01-01','End':f'{year+1}-01-01','Horizon':1,'P10':-.2,'P25':0,'P50':.05,'P75':.1,'P90':.2,'Realized CAGR':.06,'Integrity':'FULL','Survivorship complete':True,'Probability positive':.8} for year in range(1990,2020)]
    report=calibration(rows)
    assert report['Point-in-Time Integrity']=='LIMITED'
    assert report['by_horizon'][0]['Positive-return Brier score']==pytest.approx(.04)
    assert report['by_horizon'][0]['Probability reliability bins'][0]['Independent periods']==30


def test_planning_ui_handles_unvalidated_withdrawal_without_crashing():
    from streamlit.testing.v1 import AppTest
    app=AppTest.from_string('''
import sys
sys.path.insert(0,'tests')
from test_forward_planning import config
from test_v510_future_projection import market_fixture,base_inputs,YEARS
from future_projection import run_future_projection
from planning_ui import render
r=run_future_projection(market_fixture(),base_inputs(future_years=1,simulation_count=12,planning_engine=True,planning=config(solve_withdrawal=True,run_diagnostics=False)),YEARS)
render(r)
''').run(timeout=30)
    assert not app.exception
    assert any('Insufficient independent paths' in c.value for c in app.caption)
