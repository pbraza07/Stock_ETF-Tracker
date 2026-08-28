from pathlib import Path

import math
import pandas as pd

from analytics import calculate_calendar_year_returns, completed_year_labels

ROOT = Path(__file__).resolve().parents[1]


def test_completed_year_labels_are_calendar_years_not_cagr_names():
    labels = completed_year_labels(pd.Timestamp("2026-08-27"), years=10)
    assert labels == [str(y) for y in range(2025, 2015, -1)]


def test_calendar_year_return_uses_prior_and_current_year_end_adjusted_close():
    idx = pd.to_datetime([
        "2015-12-31", "2016-12-30", "2017-12-29", "2018-01-02"
    ])
    hist = pd.DataFrame({"Close": [100.0, 110.0, 88.0, 90.0]}, index=idx)
    returns = calculate_calendar_year_returns(hist, years=2, as_of=pd.Timestamp("2018-06-01"))
    assert math.isclose(returns["2017"], -0.20, rel_tol=1e-9)
    assert math.isclose(returns["2016"], 0.10, rel_tol=1e-9)


def test_partial_ipo_year_is_not_fabricated():
    idx = pd.to_datetime(["2024-06-03", "2024-12-31", "2025-12-31"])
    hist = pd.DataFrame({"Close": [50.0, 60.0, 72.0]}, index=idx)
    returns = calculate_calendar_year_returns(hist, years=2, as_of=pd.Timestamp("2026-08-27"))
    assert math.isclose(returns["2025"], 0.20, rel_tol=1e-9)
    assert returns["2024"] is None


def test_app_has_dollar_investment_simulator_and_year_sorting():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'Investment amount ($)' in app
    assert 'Include current YTD' in app
    assert 'def _investment_projection' in app
    assert 'SORT_OPTIONS = ["Market Cap", "Total Profit ($)", *PERF_COLS, "Rating"]' in app
    assert 'PERF_COLS = ["1D", "1M", "3M", "6M", "YTD", *YEAR_RETURN_COLS]' in app


def test_snapshot_uses_max_history_and_dynamic_year_columns():
    script = (ROOT / "scripts" / "update_snapshot.py").read_text(encoding="utf-8")
    assert 'MARKETSCOPE_HISTORY_PERIOD", "max"' in script
    assert 'YEAR_RETURN_COLS = completed_year_labels(as_of=now_et(), years=10)' in script
    assert '**{year: as_percent(annual_returns.get(year)) for year in YEAR_RETURN_COLS}' in script


def test_workflow_requests_max_history():
    workflow = (ROOT / ".github" / "workflows" / "update_market_snapshot.yml").read_text(encoding="utf-8")
    assert 'MARKETSCOPE_HISTORY_PERIOD: max' in workflow
    assert '(v5.9.1)' in workflow
