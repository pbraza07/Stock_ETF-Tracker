from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
PDF = (ROOT / "portfolio_simulations.py").read_text(encoding="utf-8")
RANKER = (ROOT / "scripts" / "build_actual_monthly_rankings.py").read_text(encoding="utf-8")


def test_release_version_5948():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.48"


def test_pdf_first_page_shows_marketscope_version():
    assert 'pdf_version = str(record.get("app_version") or _marketscope_version())' in PDF
    assert 'c.drawRightString(lwidth - 26, lheight - 36, f"MarketScope v{pdf_version}")' in PDF
    assert '"app_version": MARKETSCOPE_VERSION' in APP


def test_portfolio_information_table_has_positive_months_column():
    assert '"Positive months": (' in APP
    assert '"positive_months": sum(1 for v in _values if v > 0.0)' in APP
    assert '"available_months": len(_values)' in APP


def test_monthly_combo_tables_show_positive_months():
    assert '"Net Profit incl. Withdrawals ($)", "Positive Months", "Months Funded", "HWM Excluded"' in APP
    assert '"Positive Months": sim["positive_months"]' in RANKER


def test_positive_months_are_based_on_actual_monthly_portfolio_return():
    assert 'positive_months = sum(1 for row in schedule if float(row.get("portfolio_return_pct") or 0.0) > 0.0)' in APP
    assert '"positive_months": int(positive_months)' in APP
    assert 'monthly_factor > 1.0' in RANKER
    assert 'before > starting_balance' in RANKER


def test_pdf_layout_v11_forces_rebuild_and_persistence_is_protected():
    marker = "MarketScope Portfolio Split Simulator v11 - PDF version + positive months + actual monthly/yearly withdrawal results + required instrument market data on page 1"
    assert APP.count(marker) >= 2
    storage = (ROOT / "pdf_storage.py").read_text(encoding="utf-8")
    assert 'PROTECTED_SIMULATION_LIBRARY = "data/saved_portfolio_simulations.json"' in storage
    assert 'PDF_REPO_DIR = "data/generated_pdfs"' in storage


def test_existing_actual_monthly_rankings_are_enriched_without_annual_math():
    assert 'if "Positive Months" not in df.columns:' in APP
    assert 'cached_actual_monthly_returns(tuple(symbols), _years)' in APP
    assert '_start_text = str(df.iloc[0].get("Monthly Data Start") or "").strip()' in APP
    assert '_before > _start' in APP
