from pathlib import Path

import pandas as pd

from universe import BOOTSTRAP_UNIVERSE_FILE, MIN_STOCK_MARKET_CAP, UNIVERSE_FILE, load_default_universe


def test_recovery_package_ships_generated_and_bootstrap_universe_files():
    # v5.4.1 is a recovery build for the Render FileNotFoundError. It intentionally
    # ships both user-supplied universe files so the app can start immediately.
    assert UNIVERSE_FILE.exists()
    assert BOOTSTRAP_UNIVERSE_FILE.exists()
    df = load_default_universe()
    assert not df.empty
    assert "Symbol" in df.columns
    assert (df["Type"].astype(str).str.upper() == "ETF").any()
    stocks = df[df["Type"].astype(str).str.upper() == "STOCK"]
    if not stocks.empty:
        caps = pd.to_numeric(stocks["MarketCap"], errors="coerce").dropna()
        assert not caps.empty
        assert (caps > MIN_STOCK_MARKET_CAP).all()


def test_generated_snapshot_is_not_shipped_over_durable_server_data():
    root = Path(__file__).resolve().parents[1]
    assert not (root / "data" / "market_snapshot.csv").exists()
    assert (root / "data" / "market_snapshot.bootstrap.csv").exists()
