import numpy as np
import pandas as pd
import pytest
from planning_assumptions import settings,forward_cma,decomposition
from planning_paths import generate_paths,stress_correlation
from planning_cashflows import simulate,sustainable_withdrawal
from planning_validation import freeze_snapshot,walk_forward,calibration,past_bias_adjustment
from test_v510_future_projection import market_fixture,base_inputs,YEARS
from future_projection import normalize_projection_inputs,prepare_projection_model,run_future_projection,projection_cache_key

def config(**overrides):return settings({'cma_inputs':{'treasury_yield':.04,'as_of':'2026-09-20'},'solve_withdrawal':False,**overrides})
def inputs(**overrides):return normalize_projection_inputs(base_inputs(starting_investment=100000.,annual_withdrawal=10000.,future_years=2,withdrawal_frequency='Yearly',**overrides))

def test_a_historical_winner_not_forward_drift():
    c=config();a=decomposition('X','Tech',{'historical_cagr':.90},.06,1,c)
    b=decomposition('X','Tech',{'historical_cagr':-.50},.06,1,c)
    assert a['Expected geometric return']==b['Expected geometric return']
    assert a['Historical alpha']==0

def test_b_c_valuation_and_deterioration_can_be_negative():
    r=decomposition('X','Tech',{'forward_pe':200,'earnings_growth':-.8,'operating_margin':-.5,'debt_to_equity':600,'return_on_equity':-.4},.04,1,config())
    assert r['Valuation']<0
    assert r['Expected geometric return']<0

def test_d_e_horizon_prefix_and_momentum():
    model=prepare_projection_model(market_fixture(),inputs()['holdings'],YEARS,use_monthly=True)
    c=config();cma=forward_cma({},c)
    a=generate_paths(model,{},cma,c,10,16,3);b=generate_paths(model,{},cma,c,30,16,3)
    assert np.array_equal(a['returns'],b['returns'][:120])
    assert decomposition('X','Tech',{'momentum':.5},.06,20,c)['Momentum']==0
    assert decomposition('X','Tech',{},.06,1,c)['Expected geometric return']==decomposition('X','Tech',{},.06,30,c)['Expected geometric return']

def test_f_inflation_anniversary():
    i=inputs();n=len(i['holdings']);r=simulate(np.zeros((24,2,n)),i,config(inflation=.05),'Non-Rebalanced')
    amounts=r['table']['Requested spending']
    assert amounts.iloc[11]==10000
    assert amounts.iloc[23]==pytest.approx(10500)

def test_g_tax_reduces_net_and_preserves_basis():
    from planning_cashflows import liquidate
    h=np.array([[100.]]);basis=np.array([[50.]])
    net,gross,tax,sales,cost=liquidate(h,basis,np.array([100.]),config(tax_enabled=True,capital_gains_rate=.2,trading_friction=0,bid_ask=0),np.ones(1),np.zeros((1,1)))
    assert net[0]==90 and gross[0]==100 and tax[0]==10
    assert h[0,0]==0 and basis[0,0]==0

def test_h_early_crash_worse_spending_outcome():
    i=inputs();i['annual_withdrawal']=30000.;n=len(i['holdings']);r=np.zeros((24,1,n));r[0]=-.5
    late=r.copy();late[0]=0;late[-1]=-.5
    a=simulate(r,i,config(),'Non-Rebalanced');b=simulate(late,i,config(),'Non-Rebalanced')
    assert a['ending'][0]<b['ending'][0]
    assert a['summary']['Portfolio Survival Probability']<b['summary']['Portfolio Survival Probability']

def test_i_stress_correlation():
    corr=np.array([[1,.2],[.2,1.]])
    stress=stress_correlation(corr,.6)
    assert stress[0,1]>.2
    assert np.linalg.eigvalsh(stress).min()>0

def test_j_non_rebalanced_proportional_sales_preserve_drift():
    from planning_cashflows import liquidate
    h=np.array([[80.,20.]]);basis=h.copy()
    liquidate(h,basis,np.array([10.]),config(tax_enabled=False,trading_friction=0,bid_ask=0),np.array([.5,.5]),np.zeros((1,2)))
    assert np.allclose(h,[[72,18]])

def test_k_percentile_help():
    from planning_ui import PERCENTILE_HELP
    assert '10% of modeled outcomes exceed P90' in PERCENTILE_HELP
    assert '90% likely' not in PERCENTILE_HELP

def test_l_cutoff_freezes_vintages_before_selection():
    rows=[{'kind':'macro','key':'gdp','value':1,'observation_date':'2020-01-01','available_at':'2020-02-01'},
          {'kind':'macro','key':'gdp','value':9,'observation_date':'2020-01-01','available_at':'2022-01-01'}]
    assert freeze_snapshot(rows,'2020-03-01')[0]['value']==1
    def select(frozen,cutoff):
        assert len(frozen)==1 and frozen[0]['value']==1;return ['DELISTED']
    def forecast(frozen,selected,cutoff,horizon):
        assert frozen[0]['value']==1;return {f'P{p}':p/100 for p in [10,25,50,75,90]}
    result=walk_forward(rows,['2020-03-01'],select,forecast,lambda *args:{'cagr':-.8},horizons=[1])
    assert result[0]['Integrity']=='LIMITED'
    assert calibration(result)['Projection Bias']==pytest.approx(-1.3)
    assert past_bias_adjustment(result,'2020-12-01',1)==0

def test_missing_cma_never_silent_seven_percent():
    with pytest.raises(ValueError,match='No fixed 7%'):forward_cma({},settings())
    assert forward_cma({},config())['missing_components']==['valuation','institutional','history']

def test_pal_breach_and_solver():
    i=inputs();n=len(i['holdings']);r=np.zeros((24,4,n));r[0]=-.5
    result=simulate(r,i,config(pal_balance=40000,pal_rate=.1),'Non-Rebalanced')
    assert result['summary']['PAL Maintenance Breach Probability']==1
    zero=np.zeros_like(r)
    sol=sustainable_withdrawal({'returns':zero,'inflation':np.zeros((24,4)),'rates':np.zeros((24,4))},i,config(inflation=0,expense_ratio=0,trading_friction=0,bid_ask=0),'Non-Rebalanced')
    assert 49000<sol['initial_annual_withdrawal']<50001

def test_engine_exports_and_cache_sensitive_to_planning(tmp_path):
    i=base_inputs(future_years=1,simulation_count=12,planning_engine=True,planning=config())
    result=run_future_projection(market_fixture(),i,YEARS)
    assert result['planning_engine'] and len(result['strategies'])==2
    assert result['trust']['Calibration Confidence']=='UNVALIDATED'
    from planning_exports import excel_export,pdf_export
    assert excel_export(result)[:2]==b'PK'
    assert pdf_export(result).startswith(b'%PDF')
    a=projection_cache_key(i,market_fixture(),YEARS)
    i['planning']['tax_enabled']=True
    assert a!=projection_cache_key(i,market_fixture(),YEARS)

def test_real_point_in_time_runner_selects_and_forecasts_without_future_members():
    from planning_backtest import run_bundle
    rows=[]
    for symbol,sector in [('OLD','Energy'),('OTHER','Healthcare')]:
        rows.append({'kind':'universe','key':symbol,'observation_date':'2015-01-01','available_at':'2015-01-01','value':{'eligible':True,'sector':sector}})
        for year in range(2015,2021):
            rows.append({'kind':'prices','key':symbol,'observation_date':f'{year}-12-31','available_at':f'{year}-12-31','value':.05 if year%2 else -.02})
    rows.append({'kind':'universe','key':'FUTURE','observation_date':'2022-01-01','available_at':'2022-01-01','value':{'eligible':True,'sector':'Tech'}})
    rows.append({'kind':'macro','key':'treasury_10y','observation_date':'2020-12-31','available_at':'2020-12-31','value':2.})
    bundle={'records':rows,'cutoffs':['2020-12-31'],'horizons':[1],'simulation_count':8,
            'realized_annual_returns':{'OLD':{'2021':-1.},'OTHER':{'2021':.1}}}
    result=run_bundle(bundle)
    assert set(result['records'][0]['Selected'])=={'OLD','OTHER'}
    assert result['records'][0]['Realized CAGR']==pytest.approx(-.45)
    assert result['records'][0]['Integrity']=='PARTIAL'

def test_depletion_remains_recorded_after_contributions_replenish_account():
    i=inputs();i['additional_contribution']=100000.;i['withdrawal_frequency']='Monthly';i['monthly_withdrawal']=0
    r=np.zeros((24,1,len(i['holdings'])));r[0]=-1
    result=simulate(r,i,config(),'Non-Rebalanced')
    assert result['ending'][0]>0
    assert result['summary']['Probability of Depletion']==1
