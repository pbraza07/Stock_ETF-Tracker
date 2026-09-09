import pandas as pd
import pytest
from ytd_simulator import simulate_ytd

def prices():
    return pd.DataFrame({'A':[100,110,121], 'B':[100,100,100]}, index=pd.to_datetime(['2025-12-31','2026-01-02','2026-01-05']))

def test_cashflow_conservation_and_aggregation():
    for freq in ['Daily','Weekly','Monthly']:
        table, daily = simulate_ytd(prices(),1000,freq,100,'Daily',False,'2026-01-05')
        assert daily['Actual Withdrawal'].sum() == 200
        assert table.iloc[-1]['Ending Balance'] == pytest.approx(1000 + daily.Profit.sum() - 200)

def test_no_withdrawal_buy_hold():
    table, daily = simulate_ytd(prices(),1000,as_of='2026-01-05')
    assert table.iloc[-1]['Ending Balance'] == pytest.approx(1105)

def test_incomplete_month_no_withdrawal():
    _, daily = simulate_ytd(prices(),1000,withdrawal=100,as_of='2026-01-05')
    assert daily['Actual Withdrawal'].sum() == 0

def test_depletion():
    _, daily = simulate_ytd(prices(),1000,withdrawal=2000,withdrawal_frequency='Daily',as_of='2026-01-05')
    assert daily.iloc[-1]['Ending Balance'] == 0
    assert daily.Shortfall.sum() > 0

def test_missing_prior_year_rejected():
    with pytest.raises(ValueError):
        simulate_ytd(prices().iloc[1:],1000,as_of='2026-01-05')

def test_completed_month_withdraws_only_once():
    _, daily = simulate_ytd(prices(),1000,withdrawal=100,as_of='2026-02-01')
    assert daily['Actual Withdrawal'].sum() == 100
