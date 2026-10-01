import numpy as np
from test_v510_future_projection import market_fixture, base_inputs, YEARS
from future_projection import run_future_projection
from historical_calibration import sample_indices

def test_blocks_joint_and_horizon_prefix_stable():
    a=sample_indices(10,100,20,1,.25,42)
    b=sample_indices(30,100,20,1,.25,42)
    assert np.array_equal(a,b[:10])
    assert np.all(a[1]-a[0]==1)

def test_historical_returns_unaffected_by_depletion():
    def run(withdrawal):
        return run_future_projection(market_fixture(),base_inputs(projection_profile='Historical-Calibrated',future_years=5,withdrawal_frequency='Yearly',annual_withdrawal=withdrawal),YEARS)
    plain, depleted=run(0),run(1000000)
    for name in plain['strategies']:
        a=plain['strategies'][name]['table'];b=depleted['strategies'][name]['table']
        cols=[c for c in a if 'Investment Return' in c]
        assert len(cols)==5
        assert np.allclose(a[cols],b[cols])
        assert b['P50 Ending Balance'].iloc[-1]==0
    audit=plain['audit']['historical_calibration']
    assert audit['shared_periods']==6
    assert all(r['Training through']<r['Outcome through'] for r in audit['walk_forward'])
