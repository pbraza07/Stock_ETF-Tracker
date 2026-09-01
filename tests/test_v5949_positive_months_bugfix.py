from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
PDF = (ROOT / "portfolio_simulations.py").read_text(encoding="utf-8")


def test_monthly_result_no_longer_defaults_to_zero_because_key_is_missing():
    start = APP.index('def _portfolio_monthly_withdrawal_schedule(')
    end = APP.index('\ndef _finite_number', start)
    block = APP[start:end]
    assert '"positive_months": int(positive_months)' in block
    assert '"months_modeled": int(len(schedule))' in block


def test_portfolio_metric_reads_real_returned_counts():
    assert 'rb_positive = int(portfolio_monthly_withdrawal_rebalanced_result.get("positive_months") or 0)' in APP
    assert 'nr_positive = int(portfolio_monthly_withdrawal_not_rebalanced_result.get("positive_months") or 0)' in APP
    assert 'mc5.metric("Positive months", f"RB {rb_positive}/{rb_months} • NR {nr_positive}/{nr_months}")' in APP


def test_saved_pdf_record_persists_instrument_and_portfolio_positive_months():
    assert '"monthly_positive_months_rebalanced"' in APP
    assert '"monthly_positive_months_not_rebalanced"' in APP
    assert '"positive_months": (int(analytics.get("positive_months"))' in APP
    assert '"available_months": (int(analytics.get("available_months"))' in APP


def test_pdf_positive_month_counts_are_high_visibility():
    assert 'page1_positive_months = f"RB {_page1_rb_pos}/{_page1_rb_total} | NR {_page1_nr_pos}/{_page1_nr_total}"' in PDF
    assert '"POSITIVE MONTHS"' in PDF
    assert '"POS MONTHS"' in PDF
