from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
PDF = (ROOT / "portfolio_simulations.py").read_text(encoding="utf-8")


def test_version_remains_5119():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.11.9"


def test_information_table_has_one_canonical_schema_for_all_modes():
    section = APP[APP.index("def _portfolio_analytics_dataframe"):]
    section = section[:section.index("with portfolio_tab:")]
    for token in [
        '"Industry"', '"Stock"', '"Allocation"', '"10-year CAGR"',
        '"Positive years"', '"Positive months"', '"Worst year and %"',
        '"Best year and %"', '"Regular yield"', '"Est. annual dividend"',
        "*PERF_COLS", "return pd.DataFrame(rows).reindex(columns=columns)",
    ]:
        assert token in section


def test_no_withdrawal_positive_months_use_actual_monthly_returns():
    assert "def _portfolio_no_withdrawal_positive_month_counts(" in APP
    assert "analytics_monthly_payload = cached_actual_monthly_returns(" in APP
    assert '"portfolio_positive_months": (' in APP
    assert '"portfolio_available_months": (' in APP


def test_saved_legacy_no_withdrawal_records_can_be_repaired():
    assert "legacy_positive, legacy_months = _portfolio_no_withdrawal_positive_month_counts" in APP
    assert 'upgraded["portfolio_positive_months"] = int(legacy_positive)' in APP
    assert 'upgraded["portfolio_available_months"] = int(legacy_months)' in APP


def test_pdf_no_withdrawal_page1_keeps_same_information_family():
    assert '"WITHDRAWAL MODE NONE"' in PDF
    assert '"NO CASH WITHDRAWALS APPLIED"' in PDF
    assert '"FULL PORTFOLIO INFORMATION + TIMEFRAME PERFORMANCE TABLES INCLUDED"' in PDF
    assert '_base_positive_months = combined.get("positive_months")' in PDF


def test_pdf_supplemental_tables_remain_available_without_withdrawals():
    assert '"PORTFOLIO INFORMATION TABLE"' in PDF
    assert '"TIMEFRAME PERFORMANCE TABLE' in PDF
    supplemental = PDF[PDF.index("# Supplemental individual-instrument analytics tables."):]
    assert "if instruments:" in supplemental
    assert "draw_analytics_table(" in supplemental


def test_withdrawal_specific_pages_remain_conditional():
    assert 'if bool(record.get("annual_withdrawals_enabled")) and (rb_schedule or nr_schedule):' in PDF
    assert 'if bool(record.get("monthly_withdrawals_enabled")) and (mrb_schedule or mnr_schedule):' in PDF


def test_internal_pdf_contract_bumped_without_app_version_bump():
    assert "+ no-withdrawal table/PDF parity" in APP
