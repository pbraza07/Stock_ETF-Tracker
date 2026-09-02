from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
PDF = (ROOT / "portfolio_simulations.py").read_text(encoding="utf-8")
VIEWER = (ROOT / "static" / "pdf_viewer.html").read_text(encoding="utf-8")

def test_release_version():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.79"

def test_single_comparison_input_contract():
    assert '"Stocks & ETFs to compare (unlimited selection)"' in APP
    assert 'key="stock_compare_selector"' in APP
    assert 'key="comparison_enhanced_search"' not in APP
    assert 'key="comparison_add_search_results"' not in APP
    assert 'key="comparison_add_filtered"' not in APP
    assert 'key="comparison_add_all"' not in APP
    assert 'key="add_table_rows_to_comparison"' not in APP
    assert 'key=f"compare_{symbol}_{page_start}"' not in APP

def test_saved_pdf_contains_current_price_and_targets():
    assert '"current_price": (' in APP
    assert 'item.get("current_price")' in PDF
    assert 'PRICE {current_price}' in PDF
    assert 'item.get("price_target_low")' in PDF
    assert 'item.get("price_target_average")' in PDF
    assert 'item.get("price_target_high")' in PDF

def test_mobile_pdf_share_and_back_controls_preserved():
    assert 'id="backBtn"' in VIEWER
    assert 'id="shareBtn"' in VIEWER
    assert 'navigator.share' in VIEWER
    assert "window.location.href = '/'" in VIEWER
