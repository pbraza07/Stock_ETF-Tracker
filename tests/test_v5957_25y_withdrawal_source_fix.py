from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
SNAPSHOT = (ROOT / "scripts" / "update_snapshot.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "update_market_snapshot.yml").read_text(encoding="utf-8")
PDF = (ROOT / "portfolio_simulations.py").read_text(encoding="utf-8")


def test_release_version_current():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.11.2"
    assert "v5.9.66" in APP


def test_snapshot_generates_actual_monthly_history_for_full_dynamic_window():
    assert 'MONTHLY_FULL_OUT = BASE_DIR / "data" / "monthly_returns_full_history.csv"' in SNAPSHOT
    assert "MONTHLY_FULL_START_YEAR = min(int(y) for y in YEAR_RETURN_COLS)" in SNAPSHOT
    assert "MONTHLY_FULL_END_YEAR = max(int(y) for y in YEAR_RETURN_COLS)" in SNAPSHOT
    assert "calculate_monthly_returns(" in SNAPSHOT
    assert "MONTHLY_FULL_START_YEAR, MONTHLY_FULL_END_YEAR" in SNAPSHOT
    assert "monthly_full_df.to_csv" in SNAPSHOT


def test_workflow_persists_dynamic_monthly_dataset_with_annual_snapshot():
    assert "'data/monthly_returns_full_history.csv'" in WORKFLOW
    checkpoint = WORKFLOW.index("Persist verified dynamic market snapshot and monthly history")
    ranking = WORKFLOW.index("Build actual 10Y monthly withdrawal rankings")
    assert checkpoint < ranking
    assert "data/monthly_returns_full_history.csv" in WORKFLOW[checkpoint:ranking]


def test_monthly_loader_prefers_dynamic_full_history_and_retries_exact_symbol():
    assert 'MONTHLY_RETURNS_FULL_FILE = BASE_DIR / "data" / "monthly_returns_full_history.csv"' in APP
    assert 'MONTHLY_RETURNS_FULL_REPO_PATH = "data/monthly_returns_full_history.csv"' in APP
    assert 'provider.download_daily_history_since(' in APP
    assert 'start=ANNUAL_HISTORY_START' in APP
    assert 'provider.download_daily_history_since([sym], start=ANNUAL_HISTORY_START, chunk_size=1)' in APP
    assert "one Yahoo omission (e.g. LLY)" in APP


def test_monthly_returns_reconcile_to_market_table_annual_returns():
    assert "def _monthly_year_compound" in APP
    assert "def _monthly_matches_market_table" in APP
    assert "Market Table annual returns" in APP
    assert "tolerance_pp=0.05" in APP
    assert "Monthly history does not reconcile to Market Table annual returns" in APP


def test_annual_withdrawal_engine_uses_market_table_year_columns():
    assert "def _portfolio_annual_withdrawal_schedule" in APP
    assert 'lookup.loc[sym].get(str(year))' in APP
    assert '"return_method": "Market Table completed calendar-year return (Yahoo/yfinance adjusted history)"' in APP


def test_market_table_has_annual_withdrawal_simulation_using_displayed_returns():
    assert '"Table yearly withdrawal"' in APP
    assert '"Table withdrawal / year ($)"' in APP
    assert "def _market_table_annual_withdrawal_projection" in APP
    assert '"Withdrawal Years Used"' in APP
    assert '"Withdrawals Fully Funded"' in APP
    assert '"Remaining After Withdrawals ($)"' in APP
    assert '"Net Value incl. Withdrawals ($)"' in APP
    assert '"Net Profit incl. Withdrawals ($)"' in APP


def test_table_withdrawal_helper_uses_dynamic_maximum():
    assert "requested = max(1, min(ANNUAL_HISTORY_YEARS" in APP
    assert "for year in YEAR_RETURN_COLS[:requested]" in APP
    assert "for year, pct in reversed(annual)" in APP
    assert "maximum-history selection" in APP


def test_pdf_does_not_truncate_annual_withdrawal_schedule():
    assert "schedule[:21]" not in PDF
    assert "def _draw_withdrawal_detail_pages" in PDF
    assert "rows_per_page = 20" in PDF
    assert "Annual page" in PDF
    assert "Maximum-history simulations use every completed year" in PDF


def test_pdf_contract_is_v17():
    marker = 'MarketScope Portfolio Split Simulator v37 - v5.9.82 monthly reset + monthly start-year RB/NR depletion dashboard + continuous monthly start-year paths + start-year RB/NR depletion dashboard + split start-year strategies + persistent Build Simulation withdrawal tabs + annual and monthly reset views + annual positive years + display-mode searchable dropdowns + six-month universe change history + saved-card inline withdrawal summary + PDF withdrawal summary + Market Table target transcription + required instrument market data on page 1'
    assert APP.count(marker) >= 2


def test_workflow_validates_dynamic_monthly_history_before_persist():
    validator = (ROOT / "scripts" / "validate_25y_monthly.py").read_text(encoding="utf-8")
    reconcile_pos = WORKFLOW.index("Reconcile dynamic actual-monthly history to Market Table annual returns")
    persist_pos = WORKFLOW.index("Persist verified dynamic market snapshot and monthly history")
    assert reconcile_pos < persist_pos
    assert "TOLERANCE_PP = 0.05" in validator
    assert "annual return exists but 12 actual monthly returns are incomplete" in validator
    assert "annual Market Table history exists but the dynamic monthly row is missing" in validator
    assert "Dynamic monthly reconciliation passed" in validator
