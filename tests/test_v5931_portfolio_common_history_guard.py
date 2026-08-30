from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")

def test_version_5931():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.31"

def test_portfolio_period_is_limited_to_common_history():
    assert "common_history_years" in APP
    assert "portfolio_period_options" in APP
    assert "Pre-IPO/pre-inception years are not simulated" in APP

def test_missing_card_periods_are_disabled():
    assert "disabled=not _metric_available" in APP
    assert "instrument may not have existed yet" in APP
