from pathlib import Path
import pandas as pd
import numpy as np

BASE = Path(__file__).resolve().parents[1]

def _check_file(name, years, ranking):
    df = pd.read_csv(BASE / "data" / name)
    assert len(df) == 200
    assert set(years).issubset(df.columns)
    assert df[years].notna().all().all()
    assert (df["Starting Value ($)"] == 100000.0).all()
    if ranking == "profit":
        vals = pd.to_numeric(df["Total Profit ($)"], errors="raise").to_numpy()
        assert np.all(vals[:-1] >= vals[1:] - 1e-8)
    else:
        vals = pd.to_numeric(df["Worst Year %"], errors="raise").to_numpy()
        assert np.all(vals[:-1] >= vals[1:] - 1e-8)

def test_5y_rankings_cover_2025_through_2021():
    years = [str(y) for y in range(2025, 2020, -1)]
    _check_file("top200_profit_generators_5y.csv", years, "profit")
    _check_file("top200_best_worst_year_5y.csv", years, "worst")

def test_10y_rankings_cover_2025_through_2016():
    years = [str(y) for y in range(2025, 2015, -1)]
    _check_file("top200_profit_generators_10y.csv", years, "profit")
    _check_file("top200_best_worst_year_10y.csv", years, "worst")

def test_old_top50_rankings_are_removed():
    assert not (BASE / "data" / "top50_profit_generators_10y.csv").exists()
    assert not (BASE / "data" / "top50_best_worst_year_10y.csv").exists()

def test_saved_pdf_upgrade_protection_is_preserved():
    storage = (BASE / "pdf_storage.py").read_text(encoding="utf-8")
    assert 'PROTECTED_SIMULATION_LIBRARY = "data/saved_portfolio_simulations.json"' in storage
    assert 'PDF_REPO_DIR = "data/generated_pdfs"' in storage
