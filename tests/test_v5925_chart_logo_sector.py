from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
CSS = (ROOT / "styles.css").read_text(encoding="utf-8")


def test_release_version():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.47"


def test_comparison_charts_use_selected_comparison_history_set():
    assert "comparison_chart_histories = cached_card_two_year_histories(tuple(comparison_symbols))" in APP
    assert "chart_histories=comparison_chart_histories" in APP
    assert "history_map = chart_histories if chart_histories is not None else visible_chart_histories" in APP


def test_navigator_cards_use_logo_cache():
    assert "visible_logo_urls = cached_logo_urls" in APP
    assert 'logo_url=visible_logo_urls.get(symbol.upper(), "")' in APP
    assert "market-card-logo-identity" in CSS


def test_sector_performance_tab_is_stock_only_and_all_timeframes():
    assert '"◈ Sector Performance"' in APP
    assert 'market["Type"].astype(str).str.upper().eq("STOCK")' in APP
    assert 'for metric in PERF_COLS' in APP
    assert '"Equal weight", "Market-cap weighted"' in APP
    assert 'Positive Breadth %' in APP
    assert 'Bullish Ratings %' in APP
