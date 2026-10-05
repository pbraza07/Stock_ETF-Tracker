import threading
import numpy as np
import pandas as pd
import pytest
from planning_paths import generate_paths
from planning_cashflows import simulate
from planning_assumptions import settings,forward_cma
from future_projection import prepare_projection_model,normalize_projection_inputs
from test_v510_future_projection import market_fixture,base_inputs,YEARS

def test_disk_paths_identical_to_memory(tmp_path):
    inputs=normalize_projection_inputs(base_inputs())
    model=prepare_projection_model(market_fixture(),inputs['holdings'],YEARS,use_monthly=True)
    cfg=settings({'cma_inputs':{'treasury_yield':.04}});cma=forward_cma({},cfg)
    a=generate_paths(model,{},cma,cfg,2,80,123)
    b=generate_paths(model,{},cma,cfg,2,80,123,workdir=tmp_path)
    assert isinstance(b['returns'],np.memmap)
    assert np.array_equal(a['returns'],b['returns'])
    assert np.array_equal(a['inflation'],b['inflation'])

def test_balance_capture_not_required_for_identical_statistics():
    inputs=normalize_projection_inputs(base_inputs())
    returns=np.random.default_rng(3).normal(0,.02,(24,20,4))
    a=simulate(returns,inputs,settings(),'Rebalanced')
    b=simulate(returns,inputs,settings(),'Rebalanced',capture_balances=True)
    assert a['balances'].size==0 and b['balances'].shape==(24,20)
    pd.testing.assert_frame_equal(a['table'],b['table'])
    assert a['summary']==b['summary']

