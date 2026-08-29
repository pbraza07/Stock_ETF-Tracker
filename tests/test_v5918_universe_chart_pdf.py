from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
CSS = (ROOT / "styles.css").read_text(encoding="utf-8")
UNIVERSE = (ROOT / "scripts" / "update_universe.py").read_text(encoding="utf-8")
PDF = (ROOT / "portfolio_simulations.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "update_market_snapshot.yml").read_text(encoding="utf-8")


def test_universe_status_is_persisted_and_displayed():
    assert "universe_metadata.json" in UNIVERSE
    assert "added_symbols" in UNIVERSE and "removed_symbols" in UNIVERSE
    assert "Nasdaq Universe Last Refreshed" in APP
    assert "Stocks Added / Removed Today" in APP
    assert "data/universe_metadata.json" in WORKFLOW


def test_card_has_two_year_daily_chart_and_mobile_three_column_layout():
    assert 'period="2y"' in APP
    assert "2Y • 1D" in APP
    assert "card-mini-chart" in APP
    assert 'grid-template-columns: repeat(3, minmax(0, 1fr))' in CSS


def test_portfolio_default_and_pdf_first_page_fields():
    assert 'value=100_000.0' in APP
    for field in ["analyst_rating", "price_target_low", "price_target_average", "price_target_high"]:
        assert field in APP
        assert field in PDF
    assert "PORTFOLIO INSTRUMENT SNAPSHOT" in PDF
    assert "LOW {low}   AVG {avg}   HIGH {high}" in PDF
