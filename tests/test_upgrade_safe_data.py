from pathlib import Path

from universe import BOOTSTRAP_UNIVERSE_FILE, UNIVERSE_FILE, load_default_universe


def test_bootstrap_universe_loads_when_generated_file_is_not_bundled():
    assert BOOTSTRAP_UNIVERSE_FILE.exists()
    # v5.2 upgrade package intentionally does not bundle the generated file.
    assert not UNIVERSE_FILE.exists()
    df = load_default_universe()
    assert not df.empty
    assert "Symbol" in df.columns
    assert "AAPL" in set(df["Symbol"])


def test_generated_snapshot_is_not_shipped_over_durable_server_data():
    root = Path(__file__).resolve().parents[1]
    assert not (root / "data" / "market_snapshot.csv").exists()
    assert (root / "data" / "market_snapshot.bootstrap.csv").exists()
