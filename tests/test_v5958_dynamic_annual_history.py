from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
HISTORY = (ROOT / "history_config.py").read_text(encoding="utf-8")
SNAPSHOT = (ROOT / "scripts" / "update_snapshot.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "update_market_snapshot.yml").read_text(encoding="utf-8")
VERIFY = (ROOT / "scripts" / "verify_annual_returns.py").read_text(encoding="utf-8")
ANNUAL_VALIDATOR = (ROOT / "scripts" / "validate_25y_snapshot.py").read_text(encoding="utf-8")
MONTHLY_VALIDATOR = (ROOT / "scripts" / "validate_25y_monthly.py").read_text(encoding="utf-8")
PDF = (ROOT / "portfolio_simulations.py").read_text(encoding="utf-8")

from history_config import (
    annual_history_year_count,
    annual_history_year_labels,
    annual_horizon_options,
    chart_year_labels,
    rolling_completed_year_labels,
)

ET = ZoneInfo("America/New_York")


def test_release_version_5958():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.11.1"


def test_dynamic_year_count_grows_without_code_change():
    assert annual_history_year_count(datetime(2026, 9, 1, tzinfo=ET)) == 25
    assert annual_history_year_count(datetime(2027, 1, 2, tzinfo=ET)) == 26
    assert annual_history_year_count(datetime(2028, 6, 1, tzinfo=ET)) == 27
    assert annual_history_year_count(datetime(2035, 6, 1, tzinfo=ET)) == 34


def test_dynamic_year_labels_append_new_completed_year():
    years_2026 = annual_history_year_labels(datetime(2026, 9, 1, tzinfo=ET))
    assert years_2026[0] == "2025"
    assert years_2026[-1] == "2001"
    assert len(years_2026) == 25

    years_2027 = annual_history_year_labels(datetime(2027, 1, 2, tzinfo=ET))
    assert years_2027[0] == "2026"
    assert years_2027[-1] == "2001"
    assert len(years_2027) == 26


def test_horizon_controls_grow_automatically():
    options = annual_horizon_options(datetime(2027, 3, 1, tzinfo=ET))
    assert options[0] == "1Y"
    assert options[-1] == "26Y"
    assert len(options) == 26


def test_chart_years_grow_while_preserving_2001_baseline():
    labels = chart_year_labels(datetime(2028, 5, 1, tzinfo=ET), include_current=True)
    assert labels[0] == "2028"
    assert labels[-1] == "2001"


def test_fixed_horizon_products_roll_their_calendar_years():
    assert rolling_completed_year_labels(5, datetime(2027, 2, 1, tzinfo=ET)) == [
        "2026", "2025", "2024", "2023", "2022"
    ]
    assert rolling_completed_year_labels(10, datetime(2028, 2, 1, tzinfo=ET))[0] == "2027"


def test_app_has_no_hardcoded_25_year_cap():
    assert "completed_year_labels(as_of=now_et(), years=25)" not in APP
    assert "range(1, 26)" not in APP
    assert "min(25" not in APP
    assert "ANNUAL_HISTORY_YEARS = annual_history_year_count(as_of=now_et())" in APP
    assert "ANNUAL_HORIZON_OPTIONS = annual_horizon_options(as_of=now_et())" in APP


def test_snapshot_schema_is_dynamic_and_full_monthly_file_is_future_proof():
    assert "ANNUAL_HISTORY_YEARS = annual_history_year_count(as_of=now_et())" in SNAPSHOT
    assert "YEAR_RETURN_COLS = annual_history_year_labels(as_of=now_et())" in SNAPSHOT
    assert 'MONTHLY_FULL_OUT = BASE_DIR / "data" / "monthly_returns_full_history.csv"' in SNAPSHOT
    assert "MONTHLY_FULL_START_YEAR = min(int(y) for y in YEAR_RETURN_COLS)" in SNAPSHOT
    assert "MONTHLY_FULL_END_YEAR = max(int(y) for y in YEAR_RETURN_COLS)" in SNAPSHOT


def test_workflow_persists_dynamic_full_history_source():
    assert "Build dynamic annual returns and matching actual monthly history" in WORKFLOW
    assert "Audit dynamic annual-return coverage" in WORKFLOW
    assert "Reconcile dynamic actual-monthly history to Market Table annual returns" in WORKFLOW
    assert "data/monthly_returns_full_history.csv" in WORKFLOW


def test_verification_and_validators_share_dynamic_year_labels():
    assert "YEAR_COLS = annual_history_year_labels()" in VERIFY
    assert "REQUIRED_YEARS = annual_history_year_labels()" in ANNUAL_VALIDATOR
    assert "YEARS = annual_history_year_labels()" in MONTHLY_VALIDATOR


def test_pdf_dynamically_paginates_annual_history():
    assert "completed years automatically spill onto continuation pages." in PDF
    assert "for start_index in range(0, len(remaining_years), 10)" in PDF
    assert "groups_per_page = 3" in PDF
    assert "saved_years[15:25]" not in PDF


def test_pdf_contract_is_v17():
    marker = 'MarketScope Portfolio Split Simulator v37 - v5.9.82 monthly reset + monthly start-year RB/NR depletion dashboard + continuous monthly start-year paths + start-year RB/NR depletion dashboard + split start-year strategies + persistent Build Simulation withdrawal tabs + annual and monthly reset views + annual positive years + display-mode searchable dropdowns + six-month universe change history + saved-card inline withdrawal summary + PDF withdrawal summary + Market Table target transcription + required instrument market data on page 1'
    assert APP.count(marker) >= 2


def test_fixed_horizon_annual_rankings_roll_automatically_when_stale():
    ranker = (ROOT / "scripts" / "build_dynamic_annual_rankings.py").read_text(encoding="utf-8")
    assert "rolling_completed_year_labels(5)" in ranker
    assert "rolling_completed_year_labels(10)" in ranker
    assert "if not args.force and _all_outputs_current()" in ranker
    assert "top200_profit_generators_5y.csv" in ranker
    assert "top100_rebalanced_withdrawal_10y.csv" in ranker
    assert "Refresh rolling 5Y and 10Y annual ranking products when stale" in WORKFLOW
