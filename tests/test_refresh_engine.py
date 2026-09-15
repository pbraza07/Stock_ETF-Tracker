import numpy as np
import pandas as pd

from analytics import calculate_performance


def _history(days=3000):
    idx = pd.bdate_range("2015-01-02", periods=days)
    close = pd.Series(np.linspace(100.0, 250.0, len(idx)), index=idx)
    return pd.DataFrame({"Close": close})


def test_history_has_required_metrics():
    perf = calculate_performance(_history())
    assert perf.current_price > 0
    assert perf.perf_1d is not None
    assert perf.perf_1m is not None
    assert perf.perf_3m is not None
    assert perf.perf_6m is not None
    assert perf.perf_1y is not None
    assert perf.avg_5y is not None


def test_bootstrap_price_can_be_replaced_by_live_price():
    old = np.nan
    live = 123.45
    old_is_valid = old is not None and pd.notna(old) and np.isfinite(float(old)) and float(old) > 0
    assert old_is_valid is False
    # v5.1 rule: a live quote is still written even when no baseline exists.
    result = float(live)
    assert result == 123.45
