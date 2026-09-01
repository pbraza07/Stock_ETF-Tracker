from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
RANKER = (ROOT / "scripts" / "build_recession_rankings.py").read_text(encoding="utf-8")


def _usage(df):
    counts = Counter()
    for pos in range(1, 5):
        counts.update(df[f"Stock {pos}"].astype(str))
    return counts


def test_release_version_5952():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.62"
    assert "v5.9.62" in APP


def test_ranker_hard_codes_max_five_ticker_repeats():
    assert "MAX_TICKER_REPEATS = 5" in RANKER
    assert "if any(usage[s] >= MAX_TICKER_REPEATS for s in symbols)" in RANKER
    assert "assert max(usage.values()) <= MAX_TICKER_REPEATS" in RANKER


def test_role_pools_are_expanded_for_diversified_top100():
    assert "PROFIT_POOL_SIZE = 100" in RANKER
    assert "DEFENSE_POOL_SIZE = 100" in RANKER


def test_packaged_rebalanced_top100_respects_max5():
    df = pd.read_csv(ROOT / "data" / "top100_recession_balanced_rebalanced_10y.csv")
    assert len(df) == 100
    counts = _usage(df)
    assert max(counts.values()) <= 5
    assert len(counts) >= 80
    assert (df["Max Ticker Repeats"] == 5).all()


def test_packaged_not_rebalanced_top100_respects_max5():
    df = pd.read_csv(ROOT / "data" / "top100_recession_balanced_not_rebalanced_10y.csv")
    assert len(df) == 100
    counts = _usage(df)
    assert max(counts.values()) <= 5
    assert len(counts) >= 80
    assert (df["Max Ticker Repeats"] == 5).all()


def test_every_combo_keeps_two_roles_and_four_sectors():
    for filename in [
        "top100_recession_balanced_rebalanced_10y.csv",
        "top100_recession_balanced_not_rebalanced_10y.csv",
    ]:
        df = pd.read_csv(ROOT / "data" / filename)
        assert (df["Role 1"] == "Profit Engine").all()
        assert (df["Role 2"] == "Profit Engine").all()
        assert (df["Role 3"] == "Recession Defense").all()
        assert (df["Role 4"] == "Recession Defense").all()
        for _, row in df.iterrows():
            assert len({row[f"Sector {i}"] for i in range(1, 5)}) == 4


def test_app_exposes_usage_audit_columns():
    assert 'f"Stock {idx} Top100 Uses"' in APP
    assert '"Max Ticker Repeats"' in APP
    assert '"Distinct Tickers in Top 100"' in APP
    assert "maximum of five Top-100 appearances per ticker" in APP
