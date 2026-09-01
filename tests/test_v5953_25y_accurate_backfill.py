from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
SNAPSHOT = (ROOT / "scripts" / "update_snapshot.py").read_text(encoding="utf-8")
VALIDATOR = (ROOT / "scripts" / "validate_25y_snapshot.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "update_market_snapshot.yml").read_text(encoding="utf-8")
PERSISTENCE = (ROOT / "persistence.py").read_text(encoding="utf-8")


def test_release_version_current():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.54"


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


def test_no_separate_25y_repair_ui_remains():
    assert 'Repair 25Y annual history now' not in APP
    assert '25-year annual-history backfill is incomplete' not in APP
    assert 'repair_25y_annual_history' not in APP


def test_scheduled_snapshot_calculates_25_years_automatically():
    assert "YEAR_RETURN_COLS = completed_year_labels(as_of=now_et(), years=25)" in SNAPSHOT
    assert 'ANNUAL_HISTORY_START = os.getenv("MARKETSCOPE_ANNUAL_HISTORY_START", "2000-01-01")' in SNAPSHOT
    assert "calculate_calendar_year_returns(hist, years=25)" in SNAPSHOT
    assert 'provider.download_daily_history_since(' in SNAPSHOT
    assert '"annual_history_refresh_mode": "automatic explicit-start adjusted daily history"' in SNAPSHOT


def test_workflow_runs_automatic_25y_history_before_rankings():
    audit_pos = WORKFLOW.index("python scripts/validate_25y_snapshot.py")
    monthly_pos = WORKFLOW.index("python scripts/build_actual_monthly_rankings.py")
    assert audit_pos < monthly_pos
    assert 'MARKETSCOPE_ANNUAL_HISTORY_START: 2000-01-01' in WORKFLOW
    assert 'name: Refresh MarketScope universe, snapshot and actual monthly rankings (v5.9.54)' in WORKFLOW


def test_validator_keeps_schema_strict_but_allows_incremental_coverage_commits():
    assert 'REQUIRED_YEARS = [str(y) for y in range(2025, 2000, -1)]' in VALIDATOR
    assert 'OLDEST_FIVE = ["2005", "2004", "2003", "2002", "2001"]' in VALIDATOR
    assert 'MIN_OLDEST_YEAR_ROWS = 1' in VALIDATOR
    assert '25Y coverage audit warning' in VALIDATOR


def test_manual_persistence_metadata_records_annual_coverage():
    assert '"annual_history_year_count": int(len(year_cols))' in PERSISTENCE
    assert '"oldest_annual_year_with_data": oldest_annual_year' in PERSISTENCE
    assert '"annual_coverage_by_year": annual_coverage_by_year' in PERSISTENCE


def test_pdf_layout_v14_still_rebuilds_from_25y_snapshot():
    marker = "MarketScope Portfolio Split Simulator v14 - verified 25Y annual backfill + repaired positive months + actual monthly/yearly withdrawal results + required instrument market data on page 1"
    assert APP.count(marker) >= 2


def test_no_old_20y_horizon_caps_remain_in_active_app():
    assert "range(1, 21)" not in APP
    assert "min(20" not in APP
    assert "years=20" not in APP
