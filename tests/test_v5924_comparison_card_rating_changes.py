from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
UNIVERSE = (ROOT / "scripts" / "update_universe.py").read_text(encoding="utf-8")

def test_comparison_cards_mirror_card_view_features():
    assert 'comparison_detail_symbol' in APP
    assert 'render_card_profit_period_fragment(row.to_dict(), float(investment_amount), namespace="comparison")' in APP
    assert 'compare_news_' in APP
    assert 'compare_holdings_' in APP
    assert 'render_live_intraday_chart(comparison_detail_symbol)' in APP
    assert 'compare_chart_year_' in APP
    assert '_comparison_logo_html(symbol, comparison_logo_urls.get(symbol, ""))' in APP

def test_universe_tracks_analyst_rating_transitions():
    assert 'analyst_rating_changes = []' in UNIVERSE
    assert '"analyst_rating_change_count"' in UNIVERSE
    assert '"analyst_rating_changes"' in UNIVERSE
    assert 'old_rating != new_rating' in UNIVERSE
    assert 'Analyst Rating Changes' in APP
    assert 'rating_change_preview' in APP

def test_release_version():
    assert (ROOT / "VERSION.txt").read_text().strip() == "5.9.72"
