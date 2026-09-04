from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
PDF = (ROOT / "portfolio_simulations.py").read_text(encoding="utf-8")
RANKER = (ROOT / "scripts" / "build_actual_monthly_rankings.py").read_text(encoding="utf-8")


def test_release_version_current():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.11.1"


def test_pdf_first_page_shows_marketscope_version():
    assert 'pdf_version = str(record.get("app_version") or _marketscope_version())' in PDF
    assert 'c.drawRightString(lwidth - 26, lheight - 36, f"MarketScope v{pdf_version}")' in PDF
    assert '"app_version": MARKETSCOPE_VERSION' in APP


def test_portfolio_information_table_has_positive_months_column():
    assert '"Positive months": (' in APP
    assert '"positive_months": sum(1 for v in _values if v > 0.0)' in APP
    assert '"available_months": len(_values)' in APP
    assert '"positive_months": (int(analytics.get("positive_months"))' in APP
    assert '"available_months": (int(analytics.get("available_months"))' in APP


def test_monthly_combo_tables_always_expose_positive_months_near_front():
    assert '"Positive Months", "Months Funded"' in APP
    assert 'identity_cols.extend([f"Stock {idx}", f"Sector {idx}", f"Name {idx}"])' in APP
    assert 'years = COMBO_RANK_YEARS_BY_PERIOD["10Y"]' in APP
    assert 'df.at[row_idx, "Positive Months"] = positive' in APP
    assert 'f"{int(p)}/{int(t)}"' in APP
    assert '"Positive Months": sim["positive_months"]' in RANKER


def test_positive_months_are_returned_by_actual_monthly_portfolio_engine():
    monthly_start = APP.index('def _portfolio_monthly_withdrawal_schedule(')
    monthly_end = APP.index('\ndef _finite_number', monthly_start)
    block = APP[monthly_start:monthly_end]
    assert 'positive_months = sum(' in block
    assert 'row.get("portfolio_return_pct")' in block
    assert '"positive_months": int(positive_months)' in block
    assert '"months_modeled": int(len(schedule))' in block
    assert 'monthly_factor > 1.0' in RANKER
    assert 'before > starting_balance' in RANKER


def test_pdf_lists_positive_months_on_page1_strategy_page_and_instrument_table():
    assert '("POS MONTHS", page1_positive_months, cyan)' in PDF
    assert '("POSITIVE MONTHS", f"RB {mrb_positive}/{mrb_months} | NR {mnr_positive}/{mnr_months}", positive)' in PDF
    assert '"POS YEARS", "POS MONTHS"' in PDF
    assert 'pos_months = (' in PDF


def test_pdf_layout_v12_forces_rebuild_and_repairs_old_schedule_counts():
    marker = 'MarketScope Portfolio Split Simulator v37 - v5.9.82 monthly reset + monthly start-year RB/NR depletion dashboard + continuous monthly start-year paths + start-year RB/NR depletion dashboard + split start-year strategies + persistent Build Simulation withdrawal tabs + annual and monthly reset views + annual positive years + display-mode searchable dropdowns + six-month universe change history + saved-card inline withdrawal summary + PDF withdrawal summary + Market Table target transcription + required instrument market data on page 1'
    assert APP.count(marker) >= 2
    assert 'Repair old v5.9.48 records' in APP
    assert 'result["positive_months"] = int(positive)' in APP
    assert 'result["months_modeled"] = int(len(schedule))' in APP
    storage = (ROOT / "pdf_storage.py").read_text(encoding="utf-8")
    assert 'PROTECTED_SIMULATION_LIBRARY = "data/saved_portfolio_simulations.json"' in storage
    assert 'PDF_REPO_DIR = "data/generated_pdfs"' in storage


def test_existing_actual_monthly_rankings_recalculate_missing_or_invalid_counts():
    assert 'needs_enrichment = (' in APP
    assert 'cached_actual_monthly_returns(tuple(symbols), tuple(sorted(years)))' in APP
    assert 'year_factor' in APP
    assert 'df.at[row_idx, "Positive Months"] = positive' in APP
