from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
PDF = (ROOT / "portfolio_simulations.py").read_text(encoding="utf-8")

FILES = [
    ("top100_rebalanced_monthly_withdrawal_10y_no_hwm.csv", "Rebalanced monthly"),
    ("top100_not_rebalanced_monthly_withdrawal_10y_no_hwm.csv", "Not rebalanced monthly"),
]

def test_monthly_top100_files_are_complete_different_sector_and_exclude_hwm():
    for filename, strategy in FILES:
        df = pd.read_csv(ROOT / "data" / filename)
        assert len(df) == 100
        assert list(df["Rank"]) == list(range(1, 101))
        assert (df["Strategy"] == strategy).all()
        assert (df["Starting Value ($)"] == 300000.0).all()
        assert (df["Monthly Withdrawal ($)"] == 5000.0).all()
        assert (df["Total Withdrawn ($)"] == 600000.0).all()
        assert (df["Months Funded"] == 120).all()
        assert (df["Remaining Balance ($)"] > 0).all()
        assert not df["Combo"].str.contains(r"\bHWM\b", regex=True).any()
        for _, row in df.iterrows():
            stocks = [str(row[f"Stock {i}"]) for i in range(1, 5)]
            sectors = [str(row[f"Sector {i}"]) for i in range(1, 5)]
            assert len(set(stocks)) == 4
            assert len(set(sectors)) == 4

def test_monthly_rankings_descend_by_remaining_balance():
    for filename, _ in FILES:
        df = pd.read_csv(ROOT / "data" / filename)
        values = df["Remaining Balance ($)"].astype(float).tolist()
        assert all(values[i] >= values[i + 1] for i in range(len(values) - 1))

def test_portfolio_has_monthly_and_yearly_withdrawal_controls():
    assert '"Yearly withdrawal"' in APP
    assert '"Monthly withdrawal"' in APP
    assert 'key="portfolio_monthly_withdrawals_enabled"' in APP
    assert 'key="portfolio_monthly_withdrawal"' in APP
    assert "_on_yearly_withdrawal_toggle" in APP
    assert "_on_monthly_withdrawal_toggle" in APP

def test_monthly_presets_autoload_300k_5k_10y_and_exclude_hwm():
    assert 'COMBO_WITHDRAWAL_MONTHLY = 5_000.0' in APP
    assert 'top100_rebalanced_monthly_withdrawal_10y_no_hwm.csv' in APP
    assert 'top100_not_rebalanced_monthly_withdrawal_10y_no_hwm.csv' in APP
    assert 'st.session_state.portfolio_monthly_withdrawals_enabled = True' in APP
    assert 'st.session_state.portfolio_monthly_withdrawal = float(COMBO_WITHDRAWAL_MONTHLY)' in APP
    assert 'HWM is excluded from this ranking' in APP

def test_monthly_engine_uses_equivalent_monthly_rate_from_annual_returns():
    assert "def _portfolio_monthly_withdrawal_schedule" in APP
    assert "annual_factor ** (1.0 / 12.0)" in APP
    assert "not a reconstruction of actual historical monthly price paths" in APP
    assert '"period": f"{year}-{month_number:02d}"' in APP

def test_saved_record_and_pdf_contain_monthly_strategy_results():
    assert '"monthly_withdrawals_enabled": bool(portfolio_monthly_withdrawals_enabled)' in APP
    assert '"monthly_withdrawal_rebalanced_schedule"' in APP
    assert '"monthly_withdrawal_not_rebalanced_schedule"' in APP
    assert "MONTHLY WITHDRAWALS - STRATEGY COMPARISON" in PDF
    assert "MONTHLY WITHDRAWAL SCHEDULE - REBALANCED" in PDF
    assert "MONTHLY WITHDRAWAL SCHEDULE - NOT REBALANCED" in PDF
    assert 'record.get("monthly_withdrawal_rebalanced_schedule")' in PDF
    assert 'record.get("monthly_withdrawal_not_rebalanced_schedule")' in PDF
    assert "Monthly rates are equivalent rates derived from each saved annual return" in PDF

def test_pdf_layout_v9_forces_upgrade_and_persistence_stays_protected():
    marker = "MarketScope Portfolio Split Simulator v9 - monthly + yearly rebalanced/not-rebalanced withdrawal results + required instrument market data on page 1"
    assert APP.count(marker) >= 2
    storage = (ROOT / "pdf_storage.py").read_text(encoding="utf-8")
    assert 'PROTECTED_SIMULATION_LIBRARY = "data/saved_portfolio_simulations.json"' in storage
    assert 'PDF_REPO_DIR = "data/generated_pdfs"' in storage
