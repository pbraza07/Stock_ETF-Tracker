from pathlib import Path
import pandas as pd

from analytics import calculate_monthly_returns

ROOT = Path(__file__).resolve().parents[1]

def test_calculate_monthly_returns_uses_prior_month_end():
    idx = pd.to_datetime([
        "2015-12-31",
        "2016-01-29",
        "2016-02-29",
        "2016-03-31",
    ])
    hist = pd.DataFrame({"Close": [100.0, 110.0, 99.0, 108.9]}, index=idx)
    got = calculate_monthly_returns(hist, 2016, 2016)
    assert abs(got["2016-01"] - 0.10) < 1e-12
    assert abs(got["2016-02"] - (-0.10)) < 1e-12
    assert abs(got["2016-03"] - 0.10) < 1e-12
    assert got["2016-04"] is None

def test_app_has_no_equivalent_annual_to_monthly_math():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "annual_factor ** (1.0 / 12.0)" not in app
    assert "(1 + annual return)^(1/12)" not in app
    assert "cached_actual_monthly_returns" in app
    assert "_load_actual_monthly_ranked_combo_file" in app

def test_release_version():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.75"
