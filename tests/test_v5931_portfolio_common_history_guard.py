from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")

def test_version_5932():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.61"

def test_portfolio_keeps_1_to_25_year_choices_and_uses_common_start():
    assert 'portfolio_period_options = ["YTD", *ANNUAL_HORIZON_OPTIONS]' in APP
    assert "def _portfolio_common_calendar_years" in APP
    assert "def _effective_portfolio_years" in APP
    assert "Simulation starts only once every selected instrument has a valid completed-year return" in APP
    assert "effective_portfolio_years" in APP

def test_missing_card_periods_are_disabled():
    assert "disabled=not _metric_available" in APP
    assert "instrument may not have existed yet" in APP
