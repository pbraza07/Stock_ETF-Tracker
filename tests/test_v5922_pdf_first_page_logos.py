from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
PDF = (ROOT / "portfolio_simulations.py").read_text(encoding="utf-8")
YAHOO = (ROOT / "providers" / "yahoo.py").read_text(encoding="utf-8")
CSS = (ROOT / "styles.css").read_text(encoding="utf-8")


def test_release_version():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.65"


def test_pdf_page_one_required_instrument_fields():
    for token in [
        "PORTFOLIO INSTRUMENT SNAPSHOT",
        'item.get("current_price")',
        'item.get("analyst_rating")',
        'item.get("price_target_low")',
        'item.get("price_target_average")',
        'item.get("price_target_high")',
        'item.get("sector")',
        'item.get("name")',
    ]:
        assert token in PDF
    assert "required instrument market data on page 1" in APP
    assert "_force_pdf_rebuild" in APP
    assert "_enrich_pdf_record_with_current_market" in APP


def test_comparison_selected_instruments_have_logos_in_cards_and_table():
    assert "cached_logo_urls" in APP
    assert "_comparison_logo_html" in APP
    assert 'comp_table["Logo"]' in APP
    assert 'st.column_config.ImageColumn("Logo"' in APP
    assert "comparison-card-identity" in CSS
    assert "get_logo_urls_many" in YAHOO
    assert "get_logo_url" in YAHOO
    assert "logoUrl" in YAHOO
