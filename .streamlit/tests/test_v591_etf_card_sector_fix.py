from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
CSS = (ROOT / "styles.css").read_text(encoding="utf-8")


def test_card_builder_is_compact_and_used():
    assert "def _instrument_card_html" in APP
    assert "return ''.join(part for part in parts if part)" in APP
    assert "_instrument_card_html(row, price, cap_display, rating, signal)" in APP


def test_stock_sector_is_rendered_under_company_name():
    assert "def _stock_sector_html" in APP
    assert "_stock_sector_html(row)" in APP
    assert ".stock-sector" in CSS


def test_etf_price_target_empty_fragment_cannot_break_card_template():
    # Regression guard: do not go back to the indented triple-quoted card HTML
    # with an empty ETF-only interpolation between lines.
    assert 'f\'\'\'<div class="instrument-card full-metrics-card">' not in APP
    assert 'if str(row.get("Type") or "").strip().upper() != "STOCK":' in APP
    assert 'return ""' in APP
