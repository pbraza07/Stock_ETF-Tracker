from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
SNAPSHOT = (ROOT / "scripts" / "update_snapshot.py").read_text(encoding="utf-8")
VALIDATOR = (ROOT / "scripts" / "validate_25y_snapshot.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "update_market_snapshot.yml").read_text(encoding="utf-8")
PERSISTENCE = (ROOT / "persistence.py").read_text(encoding="utf-8")


def test_release_version_5953():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.53"
    assert "v5.9.53" in APP


def test_app_tracks_25_completed_years_and_oldest_five():
    assert "completed_year_labels(as_of=now_et(), years=25)" in APP
    assert "OLDEST_FIVE_YEAR_COLS = list(YEAR_RETURN_COLS[-5:])" in APP
    assert 'range(1, 26)' in APP


def test_snapshot_loader_prefers_real_25y_coverage_over_price_only():
    assert "def _annual_coverage_stats" in APP
    assert "def _snapshot_quality_key" in APP
    assert 'int(stats["years_with_any"])' in APP
    assert 'int(stats["oldest_five_cells"])' in APP
    assert 'max(pool, key=lambda pair: _snapshot_quality_key(pair[1]))' in APP


def test_targeted_25y_repair_uses_max_adjusted_history_and_persists():
    assert '↻ Repair 25Y annual history now' in APP
    assert 'provider.download_daily_history(batch, period="max")' in APP
    assert 'apply_history_refresh(repaired, histories, batch, stamp)' in APP
    assert '"Yahoo Finance max adjusted history - 25Y repair"' in APP
    assert "No placeholder values were written." in APP


def test_scheduled_snapshot_calculates_25_years():
    assert "YEAR_RETURN_COLS = completed_year_labels(as_of=now_et(), years=25)" in SNAPSHOT
    assert "calculate_calendar_year_returns(hist, years=25)" in SNAPSHOT
    assert '"annual_history_year_count": len(YEAR_RETURN_COLS)' in SNAPSHOT
    assert '"annual_coverage_by_year": annual_coverage_by_year' in SNAPSHOT


def test_workflow_validates_oldest_five_before_rankings():
    validate_pos = WORKFLOW.index("python scripts/validate_25y_snapshot.py")
    monthly_pos = WORKFLOW.index("python scripts/build_actual_monthly_rankings.py")
    assert validate_pos < monthly_pos
    assert 'name: Refresh MarketScope universe, snapshot and actual monthly rankings (v5.9.53)' in WORKFLOW


def test_validator_requires_2025_through_2001_and_real_oldest_data():
    assert 'REQUIRED_YEARS = [str(y) for y in range(2025, 2000, -1)]' in VALIDATOR
    assert 'OLDEST_FIVE = ["2005", "2004", "2003", "2002", "2001"]' in VALIDATOR
    assert "MIN_OLDEST_YEAR_ROWS = 10" in VALIDATOR
    assert "pd.to_numeric(df[year], errors=\"coerce\").notna().sum()" in VALIDATOR


def test_manual_persistence_metadata_records_annual_coverage():
    assert '"annual_history_year_count": int(len(year_cols))' in PERSISTENCE
    assert '"oldest_annual_year_with_data": oldest_annual_year' in PERSISTENCE
    assert '"annual_coverage_by_year": annual_coverage_by_year' in PERSISTENCE


def test_pdf_layout_v14_forces_saved_pdf_refresh_after_backfill():
    marker = "MarketScope Portfolio Split Simulator v14 - verified 25Y annual backfill + repaired positive months + actual monthly/yearly withdrawal results + required instrument market data on page 1"
    assert APP.count(marker) >= 2


def test_no_old_20y_horizon_caps_remain_in_active_app():
    assert "range(1, 21)" not in APP
    assert "min(20" not in APP
    assert "years=20" not in APP
