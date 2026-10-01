from pathlib import Path

import pandas as pd

import universe


def test_cp1252_universe_file_is_read(tmp_path: Path):
    p = tmp_path / "default_universe.csv"
    df = pd.DataFrame([
        {
            "Symbol": "TEST",
            "Name": "Test® Corporation",
            "Sector": "Technology",
            "Industry": "Software",
            "Type": "Stock",
            "MarketCap": 150_000_000_000,
            "Source": "Nasdaq Stock Screener",
            "SourceSymbol": "TEST",
        }
    ])
    df.to_csv(p, index=False, encoding="cp1252")
    out = universe._read_universe_file(p)
    assert out.loc[0, "Symbol"] == "TEST"
    assert out.loc[0, "Name"] == "Test® Corporation"


def test_root_level_fallback_is_accepted(tmp_path: Path, monkeypatch):
    data_generated = tmp_path / "data" / "default_universe.csv"
    data_bootstrap = tmp_path / "data" / "default_universe.bootstrap.csv"
    root_generated = tmp_path / "default_universe.csv"
    root_bootstrap = tmp_path / "default_universe.bootstrap.csv"
    root_generated.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([
        {
            "Symbol": "ROOT",
            "Name": "Root Corp",
            "Sector": "Technology",
            "Industry": "Software",
            "Type": "Stock",
            "MarketCap": 200_000_000_000,
            "Source": "Nasdaq Stock Screener",
            "SourceSymbol": "ROOT",
        }
    ]).to_csv(root_generated, index=False)

    monkeypatch.setattr(universe, "UNIVERSE_FILE", data_generated)
    monkeypatch.setattr(universe, "BOOTSTRAP_UNIVERSE_FILE", data_bootstrap)
    monkeypatch.setattr(universe, "ROOT_UNIVERSE_FILE", root_generated)
    monkeypatch.setattr(universe, "ROOT_BOOTSTRAP_UNIVERSE_FILE", root_bootstrap)

    out = universe.load_default_universe()
    assert out["Symbol"].tolist() == ["ROOT"]


def test_bootstrap_stocks_with_unknown_caps_can_start_app(tmp_path: Path, monkeypatch):
    data_generated = tmp_path / "data" / "default_universe.csv"
    data_bootstrap = tmp_path / "data" / "default_universe.bootstrap.csv"
    data_bootstrap.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([
        {
            "Symbol": "AAPL",
            "Name": "Apple Inc.",
            "Sector": "Technology",
            "Industry": "Consumer Electronics",
            "Type": "Stock",
            "MarketCap": None,
            "Source": "Bootstrap; refresh via Nasdaq screener",
            "SourceSymbol": "AAPL",
        },
        {
            "Symbol": "SPY",
            "Name": "SPDR S&P 500 ETF Trust",
            "Sector": "Broad Market",
            "Industry": "ETF / Fund",
            "Type": "ETF",
            "MarketCap": None,
            "Source": "Bootstrap ETF allowlist",
            "SourceSymbol": "SPY",
        },
    ]).to_csv(data_bootstrap, index=False)

    monkeypatch.setattr(universe, "UNIVERSE_FILE", data_generated)
    monkeypatch.setattr(universe, "BOOTSTRAP_UNIVERSE_FILE", data_bootstrap)
    monkeypatch.setattr(universe, "ROOT_UNIVERSE_FILE", tmp_path / "default_universe.csv")
    monkeypatch.setattr(universe, "ROOT_BOOTSTRAP_UNIVERSE_FILE", tmp_path / "default_universe.bootstrap.csv")

    out = universe.load_default_universe()
    assert set(out["Symbol"]) == {"AAPL", "SPY"}
