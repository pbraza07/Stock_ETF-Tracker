from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")

def test_common_start_year_contract():
    assert "_portfolio_common_calendar_years" in APP
    assert "_effective_portfolio_years" in APP
    assert "effective common history" in APP
    assert "request •" in APP and "Y effective" in APP

def test_sector_popover_profit_contract():
    assert "Clickable timeframe header" in APP
    assert "Investment basis ($ per stock)" in APP
    assert 'drill_table["Total Profit %"] = selected_returns' in APP
    assert 'drill_table["Total Profit"] = np.where' in APP
    assert '*[f"{i}Y" for i in range(1, 26)]' in APP
