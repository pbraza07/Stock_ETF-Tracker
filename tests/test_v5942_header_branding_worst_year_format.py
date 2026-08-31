from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
APP = (BASE / "app.py").read_text(encoding="utf-8")
CSS = (BASE / "styles.css").read_text(encoding="utf-8")

def test_worst_year_percentage_precedes_parenthesized_year():
    assert 'return f"{worst_return:+.2f}% ({worst_year})"' in APP

def test_header_has_small_marketscope_logo():
    assert 'class="marketscope-logo"' in APP
    assert ".marketscope-logo {" in CSS
    assert "marketscope-logo-line" in APP

def test_header_shows_current_version_below_name():
    assert '<h1>MarketScope</h1>' in APP
    assert '<div class="marketscope-version">v5.9.44</div>' in APP
    assert ".marketscope-version {" in CSS

def test_persistence_protection_remains_in_release():
    pdf_storage = (BASE / "pdf_storage.py").read_text(encoding="utf-8")
    assert 'PROTECTED_SIMULATION_LIBRARY = "data/saved_portfolio_simulations.json"' in pdf_storage
    assert 'PDF_REPO_DIR = "data/generated_pdfs"' in pdf_storage
