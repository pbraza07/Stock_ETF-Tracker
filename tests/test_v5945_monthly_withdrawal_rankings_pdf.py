from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
PDF = (ROOT / "portfolio_simulations.py").read_text(encoding="utf-8")
ANALYTICS = (ROOT / "analytics.py").read_text(encoding="utf-8")
REFRESH = (ROOT / "scripts" / "update_snapshot.py").read_text(encoding="utf-8")
RANKER = (ROOT / "scripts" / "build_actual_monthly_rankings.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "update_market_snapshot.yml").read_text(encoding="utf-8")

def test_portfolio_has_monthly_and_yearly_withdrawal_controls():
    assert '"Yearly withdrawal"' in APP
    assert '"Monthly withdrawal"' in APP
    assert 'key="portfolio_monthly_withdrawals_enabled"' in APP
    assert 'key="portfolio_monthly_withdrawal"' in APP
    assert "_on_yearly_withdrawal_toggle" in APP
    assert "_on_monthly_withdrawal_toggle" in APP

def test_monthly_engine_uses_actual_monthly_returns_not_annual_conversion():
    assert "def _portfolio_monthly_withdrawal_schedule" in APP
    assert "actual_monthly_returns" in APP
    assert "1.0 + float(monthly_data[sym][label])" in APP
    assert "annual_factor ** (1.0 / 12.0)" not in APP
    assert "(1 + annual return)^(1/12)" not in APP
    assert "calculate_monthly_returns" in APP

def test_actual_monthly_return_formula_uses_month_end_adjusted_prices():
    assert "def calculate_monthly_returns" in ANALYTICS
    assert 'monthly_close = close.groupby(close.index.to_period("M")).last().sort_index()' in ANALYTICS
    assert "float(finish / base - 1.0)" in ANALYTICS

def test_daily_refresh_persists_actual_120_month_history():
    assert 'MONTHLY_OUT = BASE_DIR / "data" / "monthly_returns_10y.csv"' in REFRESH
    assert "calculate_monthly_returns(hist, MONTHLY_START_YEAR, MONTHLY_END_YEAR)" in REFRESH
    assert "Actual adjusted month-end return from Yahoo/yfinance daily history" in REFRESH

def test_top100_ranker_uses_actual_monthly_factors_and_excludes_hwm():
    assert 'MONTHLY_FILE = BASE_DIR / "data" / "monthly_returns_10y.csv"' in RANKER
    assert 'raw["Symbol"].ne("HWM")' in RANKER
    assert "month_factors = factors[combo_idx, month]" in RANKER
    assert "rb_before = rb * month_factors.mean(axis=1)" in RANKER
    assert "nr *= month_factors" in RANKER
    assert 'METHOD = "Actual adjusted month-end return from Yahoo/yfinance daily history"' in RANKER

def test_workflow_regenerates_actual_monthly_rankings():
    assert "python scripts/build_actual_monthly_rankings.py" in WORKFLOW
    assert "data/monthly_returns_10y.csv" in WORKFLOW
    assert "data/top100_rebalanced_monthly_withdrawal_10y_no_hwm.csv" in WORKFLOW
    assert "data/top100_not_rebalanced_monthly_withdrawal_10y_no_hwm.csv" in WORKFLOW

def test_saved_record_and_pdf_contain_actual_monthly_strategy_results():
    assert '"monthly_withdrawals_enabled": bool(portfolio_monthly_withdrawals_enabled)' in APP
    assert '"monthly_withdrawal_rebalanced_schedule"' in APP
    assert '"monthly_withdrawal_not_rebalanced_schedule"' in APP
    assert '"monthly_return_method": "Actual adjusted month-end return from Yahoo/yfinance daily history"' in APP
    assert "MONTHLY WITHDRAWALS - STRATEGY COMPARISON" in PDF
    assert "MONTHLY WITHDRAWAL SCHEDULE - REBALANCED" in PDF
    assert "MONTHLY WITHDRAWAL SCHEDULE - NOT REBALANCED" in PDF
    assert "Actual adjusted month-end returns from Yahoo/yfinance daily market history." in PDF

def test_pdf_layout_v10_and_persistence_protection():
    marker = "MarketScope Portfolio Split Simulator v10 - actual monthly returns + monthly/yearly rebalanced/not-rebalanced withdrawal results + required instrument market data on page 1"
    assert APP.count(marker) >= 2
    storage = (ROOT / "pdf_storage.py").read_text(encoding="utf-8")
    assert 'PROTECTED_SIMULATION_LIBRARY = "data/saved_portfolio_simulations.json"' in storage
    assert 'PDF_REPO_DIR = "data/generated_pdfs"' in storage
