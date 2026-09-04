from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
SNAPSHOT = (ROOT / "scripts" / "update_snapshot.py").read_text(encoding="utf-8")
PDF = (ROOT / "portfolio_simulations.py").read_text(encoding="utf-8")
HISTORY = (ROOT / "history_config.py").read_text(encoding="utf-8")


def test_app_requests_dynamic_completed_years_and_clickable_tiles():
    assert "YEAR_RETURN_COLS = annual_history_year_labels(as_of=now_et())" in APP
    assert 'PERF_COLS = ["1D", "1M", "3M", "6M", "YTD", *YEAR_RETURN_COLS]' in APP
    assert "for idx in range(0, len(PERF_COLS), 3)" in APP


def test_snapshot_refresh_populates_dynamic_completed_years_from_explicit_start_history():
    assert "ANNUAL_HISTORY_START" in SNAPSHOT
    assert "YEAR_RETURN_COLS = annual_history_year_labels(as_of=now_et())" in SNAPSHOT
    assert "calculate_calendar_year_returns(hist, years=ANNUAL_HISTORY_YEARS)" in SNAPSHOT
    assert 'MARKETSCOPE_ANNUAL_HISTORY_START' in HISTORY


def test_pdf_splits_dynamic_history_into_paginated_bands():
    assert "completed annual returns are dynamically paginated into legible timeframe bands" in PDF
    assert "saved_years[:5]" in PDF
    assert "remaining_years = saved_years[5:]" in PDF
    assert "for start_index in range(0, len(remaining_years), 10)" in PDF
    assert "groups_per_page = 3" in PDF
