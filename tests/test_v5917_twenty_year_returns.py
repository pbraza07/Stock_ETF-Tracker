from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_app_requests_twenty_completed_years_and_clickable_tiles():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'YEAR_RETURN_COLS = completed_year_labels(as_of=now_et(), years=20)' in app
    assert 'PERF_COLS = ["1D", "1M", "3M", "6M", "YTD", *YEAR_RETURN_COLS]' in app
    assert 'for idx in range(0, len(PERF_COLS), 3):' in app
    assert 'on_click=_set_card_profit_period' in app
    assert 'range(1, 21)' in app
    assert 'range(0, 21)' in app


def test_snapshot_refresh_populates_twenty_completed_years_from_max_history():
    script = (ROOT / "scripts" / "update_snapshot.py").read_text(encoding="utf-8")
    assert 'MARKETSCOPE_HISTORY_PERIOD", "max"' in script
    assert 'YEAR_RETURN_COLS = completed_year_labels(as_of=now_et(), years=20)' in script
    assert 'calculate_calendar_year_returns(hist, years=20)' in script


def test_pdf_splits_twenty_year_history_into_legible_bands():
    source = (ROOT / "portfolio_simulations.py").read_text(encoding="utf-8")
    assert 'saved_years[:10]' in source
    assert 'saved_years[10:20]' in source
    assert 'OLDER COMPLETED CALENDAR YEARS' in source
