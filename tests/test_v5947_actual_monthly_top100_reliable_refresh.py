from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "update_market_snapshot.yml").read_text(encoding="utf-8")

def test_version_5947():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.51"
    assert "v5.9.51" in APP

def test_monthly_dropdowns_explicitly_use_actual_return_rankings():
    assert 'st.popover("🗓️ 10Y Actual-Monthly Withdrawal"' in APP
    assert "Rebalanced Monthly" in APP
    assert "Not Rebalanced Monthly" in APP
    assert "_load_actual_monthly_ranked_combo_file" in APP
    assert "Actual adjusted month-end returns from Yahoo/yfinance daily history" in APP

def test_monthly_assumptions_remain_300k_5k_10y_and_hwm_excluded():
    assert "COMBO_WITHDRAWAL_START = 300_000.0" in APP
    assert "COMBO_WITHDRAWAL_MONTHLY = 5_000.0" in APP
    assert 'st.session_state.portfolio_period = "10Y"' in APP
    assert "HWM is excluded from this ranking" in APP

def test_yearly_and_monthly_controls_are_present_and_mutually_exclusive():
    assert '"Yearly withdrawal"' in APP
    assert '"Monthly withdrawal"' in APP
    assert "_on_yearly_withdrawal_toggle" in APP
    assert "_on_monthly_withdrawal_toggle" in APP

def test_pdf_and_saved_data_commits_do_not_retrigger_long_refresh():
    assert "data/saved_portfolio_simulations.json" in WORKFLOW
    assert "data/generated_pdfs/**" in WORKFLOW
    assert "static/generated_pdfs/**" in WORKFLOW

def test_actual_monthly_ranking_workflow_still_runs():
    assert "python scripts/build_actual_monthly_rankings.py" in WORKFLOW
    assert "data/monthly_returns_10y.csv" in WORKFLOW
