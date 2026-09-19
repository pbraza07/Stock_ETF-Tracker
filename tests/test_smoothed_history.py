import numpy as np
from historical_calibration import SmoothedHistory, sample_indices


def test_non_degenerate_history_not_literal_replay_and_reproducible():
    matrix=np.array([[-.25,-.1],[.1,.07],[.4,.2],[.08,.04],[.2,.12],[.03,-.04]])
    ix=sample_indices(6,1000,len(matrix),1,.25,9)
    a=SmoothedHistory(matrix,1,.25,9);b=SmoothedHistory(matrix,1,.25,9)
    for year in range(6):
        values=a.draw(ix[year],year)
        assert np.array_equal(values,b.draw(ix[year],year))
        assert len(np.unique(values[:,0]))>900
        assert (values>-1).all()


def test_conditional_log_moments_preserved_not_volatility_inflation():
    matrix=np.array([[-.25,-.1],[.1,.07],[.4,.2],[.08,.04],[.2,.12],[.03,-.04]])
    ix=sample_indices(2,150000,len(matrix),1,0,23)
    sampler=SmoothedHistory(matrix,1,0,23)
    values=np.log1p(sampler.draw(ix[0],0))
    base=np.log1p(matrix[:-1])
    assert np.allclose(values.mean(axis=0),base.mean(axis=0),atol=.002)
    assert np.allclose(np.cov(values.T,bias=True),np.cov(base.T,bias=True),rtol=.025,atol=.0001)


def test_constant_history_does_not_invent_variation():
    matrix=np.zeros((6,2))
    sampler=SmoothedHistory(matrix,1,0,1)
    assert np.array_equal(sampler.draw(np.array([0,1,2]),0),np.zeros((3,2)))
