from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
SNAPSHOT = (ROOT / "scripts" / "update_snapshot.py").read_text(encoding="utf-8")
PDF = (ROOT / "portfolio_simulations.py").read_text(encoding="utf-8")

def test_release_version_5950():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.55"
    assert "v5.9.55" in APP

def test_app_uses_25_completed_calendar_years():
    assert "completed_year_labels(as_of=now_et(), years=25)" in APP
    assert 'range(1, 26)' in APP
    assert 'annual_return_cols = list(YEAR_RETURN_COLS[:25])' in APP
    assert 'range(0, 26)' in APP

def test_portfolio_horizons_are_capped_at_25_years():
    assert "max_years: int = 25" in APP
    assert 'min(25, int(str(period_choice).replace("Y", "")))' in APP
    assert 'min(25, int(period_choice.replace("Y", "")))' in APP
    assert "_portfolio_common_calendar_years(market_df, symbols, 25)" in APP

def test_snapshot_refresh_calculates_25_annual_returns():
    assert "completed_year_labels(as_of=now_et(), years=25)" in SNAPSHOT
    assert "calculate_calendar_year_returns(hist, years=25)" in SNAPSHOT

def test_pdf_displays_all_25_annual_returns_across_three_bands():
    assert "25 annual returns are split into three legible timeframe bands" in PDF
    assert "saved_years[:5]" in PDF
    assert "saved_years[5:15]" in PDF
    assert "saved_years[15:25]" in PDF
    assert "EARLIEST COMPLETED CALENDAR YEARS" in PDF

def test_combo_ranking_windows_remain_5y_and_10y():
    assert '"5Y": [str(y) for y in range(2025, 2020, -1)]' in APP
    assert '"10Y": [str(y) for y in range(2025, 2015, -1)]' in APP

def test_persistence_protection_remains():
    storage = (ROOT / "pdf_storage.py").read_text(encoding="utf-8")
    assert 'PROTECTED_SIMULATION_LIBRARY = "data/saved_portfolio_simulations.json"' in storage
    assert 'PDF_REPO_DIR = "data/generated_pdfs"' in storage

def test_saved_pdf_upgrade_refreshes_25y_performance_and_forces_v13():
    marker = "MarketScope Portfolio Split Simulator v14 - verified 25Y annual backfill + repaired positive months + actual monthly/yearly withdrawal results + required instrument market data on page 1"
    assert APP.count(marker) >= 2
    assert "for metric in PERF_COLS:" in APP
    assert 'item["performance"] = performance' in APP
