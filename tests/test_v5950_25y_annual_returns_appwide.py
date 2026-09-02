from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
SNAPSHOT = (ROOT / "scripts" / "update_snapshot.py").read_text(encoding="utf-8")
PDF = (ROOT / "portfolio_simulations.py").read_text(encoding="utf-8")


def test_release_version_current():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.72"


def test_app_uses_dynamic_completed_calendar_years():
    assert "ANNUAL_HISTORY_YEARS = annual_history_year_count(as_of=now_et())" in APP
    assert "YEAR_RETURN_COLS = annual_history_year_labels(as_of=now_et())" in APP
    assert "ANNUAL_HORIZON_OPTIONS = annual_horizon_options(as_of=now_et())" in APP


def test_portfolio_horizons_use_dynamic_ceiling():
    assert "max_years: int | None = None" in APP
    assert 'min(ANNUAL_HISTORY_YEARS, int(str(period_choice).replace("Y", "")))' in APP
    assert "_portfolio_common_calendar_years(market_df, symbols, ANNUAL_HISTORY_YEARS)" in APP


def test_snapshot_refresh_calculates_dynamic_annual_returns():
    assert "ANNUAL_HISTORY_YEARS = annual_history_year_count(as_of=now_et())" in SNAPSHOT
    assert "YEAR_RETURN_COLS = annual_history_year_labels(as_of=now_et())" in SNAPSHOT
    assert "calculate_calendar_year_returns(hist, years=ANNUAL_HISTORY_YEARS)" in SNAPSHOT


def test_pdf_displays_dynamic_annual_returns_across_paginated_bands():
    assert "completed annual returns are dynamically paginated into legible timeframe bands" in PDF
    assert "remaining_years = saved_years[5:]" in PDF
    assert "for start_index in range(0, len(remaining_years), 10)" in PDF
    assert "groups_per_page = 3" in PDF


def test_combo_ranking_windows_remain_fixed_horizons_but_roll_dates():
    assert '"5Y": rolling_completed_year_labels(5, as_of=now_et())' in APP
    assert '"10Y": rolling_completed_year_labels(10, as_of=now_et())' in APP


def test_persistence_protection_remains():
    storage = (ROOT / "pdf_storage.py").read_text(encoding="utf-8")
    assert 'PROTECTED_SIMULATION_LIBRARY = "data/saved_portfolio_simulations.json"' in storage
    assert 'PDF_REPO_DIR = "data/generated_pdfs"' in storage


def test_saved_pdf_upgrade_refreshes_dynamic_performance_and_forces_v17():
    marker = "MarketScope Portfolio Split Simulator v30 - v5.9.72 annual positive years + display-mode searchable dropdowns + six-month universe change history + saved-card inline withdrawal summary + PDF withdrawal summary + Market Table target transcription + required instrument market data on page 1"
    assert APP.count(marker) >= 2
    assert "for metric in PERF_COLS:" in APP
    assert 'item["performance"] = performance' in APP
