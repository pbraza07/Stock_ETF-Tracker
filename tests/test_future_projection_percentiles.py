from __future__ import annotations

import numpy as np

import future_projection as fp


def test_profit_percent_uses_total_wealth_profit_over_starting_capital():
    values = np.asarray([-50.0, 0.0, 100.0, 250.0])
    result = fp._profit_percent(values, 100.0)
    assert np.allclose(result, [-50.0, 0.0, 100.0, 250.0])


def test_percentile_helper_returns_exact_quartiles():
    values = np.asarray([100.0, 200.0, 300.0, 400.0])
    assert fp._percentile(values, 25) == 175.0
    assert fp._percentile(values, 50) == 250.0
    assert fp._percentile(values, 75) == 325.0
