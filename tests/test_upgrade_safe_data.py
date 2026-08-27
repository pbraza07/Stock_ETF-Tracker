from pathlib import Path

from universe import BOOTSTRAP_UNIVERSE_FILE, MIN_STOCK_MARKET_CAP, UNIVERSE_FILE, load_default_universe


def test_bootstrap_universe_loads_when_generated_file_is_not_bundled():
    assert BOOTSTRAP_UNIVERSE_FILE.exists()
    assert not UNIVERSE_FILE.exists()
    df = load_default_universe()
    assert not df.empty
    assert "Symbol" in df.columns
    assert (df["Type"].astype(str).str.upper() == "ETF").any()
    stocks = df[df["Type"].astype(str).str.upper() == "STOCK"]
    if not stocks.empty:
        caps = stocks["MarketCap"].astype(float)
        assert (caps > MIN_STOCK_MARKET_CAP).all()


def test_generated_snapshot_is_not_shipped_over_durable_server_data():
    root = Path(__file__).resolve().parents[1]
    assert not (root / "data" / "market_snapshot.csv").exists()
    assert (root / "data" / "market_snapshot.bootstrap.csv").exists()
