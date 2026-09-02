from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
PDF = (ROOT / "portfolio_simulations.py").read_text(encoding="utf-8")


def test_release_version_5959():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.74"


def test_pdf_contract_bumped_to_v18():
    marker = 'MarketScope Portfolio Split Simulator v32 - v5.9.74 annual reset inside withdrawal tabs + annual reset withdrawal factor + annual positive years + display-mode searchable dropdowns + six-month universe change history + saved-card inline withdrawal summary + PDF withdrawal summary + Market Table target transcription + required instrument market data on page 1'
    assert APP.count(marker) >= 2


def test_monthly_comparison_removes_misleading_december_only_return():
    assert '"REBAL. DEC RETURN"' not in PDF
    assert '"NOT REBAL. DEC RETURN"' not in PDF
    assert '"YEAR RETURN RB / NR"' in PDF


def test_year_return_compounds_all_monthly_returns():
    assert "factor *= 1.0 + pct / 100.0" in PDF
    assert '"return_pct": year_return' in PDF
    assert "YEAR RETURN = compounded Jan-Dec portfolio returns before withdrawals." in PDF


def test_yearly_cash_flow_reconciliation_fields_are_present():
    for token in [
        '"START BALANCE RB / NR"',
        '"YEAR WITHDRAWN RB / NR"',
        '"RB YEAR-END"',
        '"RB END + WITHDRAWN"',
        '"NR YEAR-END"',
        '"NR END + WITHDRAWN"',
        '"TOTAL VALUE DIFF"',
    ]:
        assert token in PDF


def test_full_year_cash_target_and_total_withdrawal_explanation_present():
    assert '"FULL-YEAR CASH TARGET"' in PDF
    assert "annual_cash_target = monthly_withdrawal * 12.0" in PDF
    assert "Remaining + cumulative withdrawals" in PDF
    assert "It reconciles cash flow; it is not the formula used for YEAR RETURN." in PDF
