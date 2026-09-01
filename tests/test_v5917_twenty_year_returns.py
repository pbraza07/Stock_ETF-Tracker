from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
SNAPSHOT = (ROOT / "scripts" / "update_snapshot.py").read_text(encoding="utf-8")
PDF = (ROOT / "portfolio_simulations.py").read_text(encoding="utf-8")

def test_app_requests_twenty_five_completed_years_and_clickable_tiles():
    assert "YEAR_RETURN_COLS = completed_year_labels(as_of=now_et(), years=25)" in APP
    assert 'PERF_COLS = ["1D", "1M", "3M", "6M", "YTD", *YEAR_RETURN_COLS]' in APP
    assert "for idx in range(0, len(PERF_COLS), 3)" in APP

def test_snapshot_refresh_populates_twenty_five_completed_years_from_max_history():
    assert 'HISTORY_PERIOD = os.getenv("MARKETSCOPE_HISTORY_PERIOD", "max")' in SNAPSHOT
    assert "YEAR_RETURN_COLS = completed_year_labels(as_of=now_et(), years=25)" in SNAPSHOT
    assert "calculate_calendar_year_returns(hist, years=25)" in SNAPSHOT

def test_pdf_splits_twenty_five_year_history_into_legible_bands():
    assert "25 annual returns are split into three legible timeframe bands" in PDF
    assert "saved_years[:5]" in PDF
    assert "saved_years[5:15]" in PDF
    assert "saved_years[15:25]" in PDF
