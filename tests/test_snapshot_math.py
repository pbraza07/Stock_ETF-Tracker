import math


def update_total_return(old_pct, ratio):
    return ((1 + old_pct / 100) * ratio - 1) * 100


def update_cagr(old_pct, ratio, years):
    factor = (1 + old_pct / 100) ** years
    return ((factor * ratio) ** (1 / years) - 1) * 100


def test_total_return_overlay():
    # Snapshot: +20% from base, then price rises another 10% intraday.
    assert math.isclose(update_total_return(20, 1.10), 32.0, rel_tol=1e-9)


def test_cagr_overlay():
    v = update_cagr(10, 1.10, 5)
    assert v > 10
