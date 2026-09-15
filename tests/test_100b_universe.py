import pandas as pd

from scripts.update_universe import MIN_MARKET_CAP, _normalize_frame
from universe import _enforce_100b_universe


def test_nasdaq_frame_keeps_only_strictly_above_100b():
    df = pd.DataFrame(
        {
            "symbol": ["BIG", "EDGE", "SMALL"],
            "name": ["Big Corp", "Edge Corp", "Small Corp"],
            "marketCap": ["$100.01B", "$100B", "$99.99B"],
            "sector": ["Technology", "Technology", "Technology"],
            "industry": ["Software", "Software", "Software"],
        }
    )
    out = _normalize_frame(df, "Nasdaq Stock Screener")
    assert MIN_MARKET_CAP == 100_000_000_000.0
    assert out["Symbol"].tolist() == ["BIG"]


def test_defensive_loader_drops_legacy_sub_100b_but_keeps_etf_and_manual():
    df = pd.DataFrame(
        [
            {"Symbol": "BIG", "Type": "Stock", "MarketCap": 150_000_000_000, "Source": "Nasdaq Stock Screener"},
            {"Symbol": "OLD", "Type": "Stock", "MarketCap": 5_000_000_000, "Source": "Nasdaq Stock Screener"},
            {"Symbol": "MAN", "Type": "Stock", "MarketCap": 5_000_000_000, "Source": "Yahoo search / manual persistent add"},
            {"Symbol": "SPY", "Type": "ETF", "MarketCap": None, "Source": "User ETF allowlist"},
        ]
    )
    out = _enforce_100b_universe(df)
    assert set(out["Symbol"]) == {"BIG", "MAN", "SPY"}
