from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
SNAPSHOT = (ROOT / "scripts" / "update_snapshot.py").read_text(encoding="utf-8")
VALIDATOR = (ROOT / "scripts" / "validate_25y_snapshot.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "update_market_snapshot.yml").read_text(encoding="utf-8")
PERSISTENCE = (ROOT / "persistence.py").read_text(encoding="utf-8")


def test_release_version_current():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.67"


def test_app_tracks_dynamic_completed_years_and_oldest_five():
    assert "ANNUAL_HISTORY_YEARS = annual_history_year_count(as_of=now_et())" in APP
    assert "YEAR_RETURN_COLS = annual_history_year_labels(as_of=now_et())" in APP
    assert "OLDEST_FIVE_YEAR_COLS = list(YEAR_RETURN_COLS[-5:])" in APP
    assert "ANNUAL_HORIZON_OPTIONS = annual_horizon_options(as_of=now_et())" in APP


def test_snapshot_loader_prefers_real_full_history_coverage_over_price_only():
    assert "def _annual_coverage_stats" in APP
    assert "def _snapshot_quality_key" in APP
    assert 'int(stats["years_with_any"])' in APP
    assert 'int(stats["oldest_five_cells"])' in APP
    assert 'source_priority = {"bootstrap": 0, "local": 1, "github": 2}' in APP
    assert "_snapshot_quality_key(pair[1])" in APP


def test_no_separate_history_repair_ui_remains():
    assert 'Repair 25Y annual history now' not in APP
    assert 'repair_25y_annual_history' not in APP


def test_scheduled_snapshot_calculates_dynamic_years_automatically():
    assert "ANNUAL_HISTORY_YEARS = annual_history_year_count(as_of=now_et())" in SNAPSHOT
    assert "YEAR_RETURN_COLS = annual_history_year_labels(as_of=now_et())" in SNAPSHOT
    assert "calculate_calendar_year_returns(hist, years=ANNUAL_HISTORY_YEARS)" in SNAPSHOT
    assert 'provider.download_daily_history_since(' in SNAPSHOT
    assert '"annual_history_refresh_mode": "automatic explicit-start adjusted daily history"' in SNAPSHOT


def test_workflow_runs_dynamic_history_before_rankings():
    audit_pos = WORKFLOW.index("python scripts/validate_25y_snapshot.py")
    monthly_pos = WORKFLOW.index("python scripts/build_actual_monthly_rankings.py")
    assert audit_pos < monthly_pos
    assert 'MARKETSCOPE_ANNUAL_HISTORY_START: 2000-01-01' in WORKFLOW
    assert 'name: Refresh MarketScope universe, snapshot and actual monthly rankings (v5.9.67)' in WORKFLOW


def test_validator_schema_is_dynamic():
    assert "REQUIRED_YEARS = annual_history_year_labels()" in VALIDATOR
    assert "OLDEST_FIVE = REQUIRED_YEARS[-5:]" in VALIDATOR
    assert "MIN_OLDEST_YEAR_ROWS = 1" in VALIDATOR
    assert "next completed calendar year will be added automatically" in VALIDATOR


def test_manual_persistence_metadata_records_annual_coverage():
    assert '"annual_history_year_count": int(len(year_cols))' in PERSISTENCE
    assert '"oldest_annual_year_with_data": oldest_annual_year' in PERSISTENCE
    assert '"annual_coverage_by_year": annual_coverage_by_year' in PERSISTENCE


def test_pdf_layout_v17_rebuilds_from_dynamic_snapshot():
    marker = "MarketScope Portfolio Split Simulator v25 - v5.9.66 end-to-end analyst target restore + manual universe refresh + responsive withdrawal KPI layout + required instrument market data on page 1"
    assert APP.count(marker) >= 2


def test_no_old_fixed_horizon_caps_remain_in_active_app():
    assert "range(1, 21)" not in APP
    assert "min(20" not in APP
    assert "years=20" not in APP
    assert "range(1, 26)" not in APP
    assert "min(25" not in APP
