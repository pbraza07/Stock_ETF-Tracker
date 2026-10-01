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

def test_missing_prior_year_uses_explicit_partial_start():
    table, daily = simulate_ytd(prices().iloc[1:],1000,as_of='2026-01-05')
    assert not daily.attrs['full_ytd']
    assert daily.attrs['start_date'] == '2026-01-02'
    assert table.iloc[-1]['Ending Balance'] == pytest.approx(1050)

def test_timezone_alignment_and_missing_holdings():
    from ytd_simulator import history_prices
    histories = {s: pd.DataFrame({'Close':[100,110]}, index=pd.date_range('2025-12-31', periods=2, tz=tz))
                 for s, tz in [('A','America/New_York'), ('B','Europe/London')]}
    assert len(history_prices(histories,['A','B']).dropna()) == 2
    with pytest.raises(ValueError, match='C'):
        history_prices(histories,['A','C'])

def test_saved_snapshot_counts_returns_before_withdrawals():
    import json
    from ytd_simulator import make_saved_record
    output = simulate_ytd(prices(),1000,withdrawal=100,withdrawal_frequency='Daily',as_of='2026-01-05')
    record = make_saved_record({'Non-Rebalanced':output},{'principal':1000},'Example')
    saved = json.loads(json.dumps(record))['strategies']['Non-Rebalanced']['snapshot']
    assert saved['Positive Days'] == 2
    assert saved['Positive Months'] == 1
    assert saved['Beginning Balance'] == 1000
    assert saved['Current Balance'] < 1000
    output[1].iloc[0,0] = 0
    assert record['strategies']['Non-Rebalanced']['snapshot']['Beginning Balance'] == 1000

def test_insufficient_current_history_still_explained():
    with pytest.raises(ValueError, match='two shared'):
        simulate_ytd(prices().iloc[-1:],1000,as_of='2026-01-05')

def test_completed_month_withdraws_only_once():
    _, daily = simulate_ytd(prices(),1000,withdrawal=100,as_of='2026-02-01')
    assert daily['Actual Withdrawal'].sum() == 100
