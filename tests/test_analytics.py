import pandas as pd

from analytics import calculate_performance


def test_positive_returns():
    idx = pd.date_range("2015-01-02", "2026-01-02", freq="B")
    close = pd.Series(range(100, 100 + len(idx)), index=idx, dtype=float)
    result = calculate_performance(pd.DataFrame({"Close": close}), as_of=pd.Timestamp("2026-01-02 12:00:00"))
    assert result.since_inception is not None and result.since_inception > 0
    assert result.avg_10y is not None and result.avg_10y > 0
    assert result.avg_5y is not None and result.avg_5y > 0


def test_short_history_blanks_long_horizon():
    idx = pd.date_range("2024-01-02", "2026-01-02", freq="B")
    close = pd.Series(range(100, 100 + len(idx)), index=idx, dtype=float)
    result = calculate_performance(pd.DataFrame({"Close": close}), as_of=pd.Timestamp("2026-01-02 12:00:00"))
    assert result.avg_5y is None
    assert result.avg_10y is None
