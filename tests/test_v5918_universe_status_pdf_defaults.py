from pathlib import Path

from portfolio_simulations import build_portfolio_simulation_pdf

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
UNIVERSE = (ROOT / "scripts" / "update_universe.py").read_text(encoding="utf-8")
SNAPSHOT = (ROOT / "scripts" / "update_snapshot.py").read_text(encoding="utf-8")
PDF_SOURCE = (ROOT / "portfolio_simulations.py").read_text(encoding="utf-8")


def test_release_version_5918():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.18"


def test_default_sort_is_1d_high_to_low_and_portfolio_starts_100k():
    assert '_query_scalar_early("sort_choice", "1D")' in APP
    assert 'st.session_state.card_sort_choice = "1D"' in APP
    assert 'st.session_state.card_sort_ascending = False' in APP
    assert 'st.session_state.table_sort_choice = "1D"' in APP
    assert 'st.session_state.table_sort_direction = "High → Low"' in APP
    assert 'st.session_state.portfolio_total_amount = 100_000.0' in APP
    assert 'value=100_000.0' in APP


def test_nasdaq_universe_status_and_membership_delta_contract():
    for token in [
        "NASDAQ UNIVERSE LAST REFRESHED",
        "STOCKS ADDED / REMOVED TODAY",
        "nasdaq_universe_refreshed_at_display_et",
        "nasdaq_stocks_added_count",
        "nasdaq_stocks_removed_count",
    ]:
        assert token in APP or token in UNIVERSE or token in SNAPSHOT
    assert 'current_stock_symbols - prior_stock_symbols' in UNIVERSE
    assert 'prior_stock_symbols - current_stock_symbols' in UNIVERSE
    assert 'UNIVERSE_STATE' in UNIVERSE and 'UNIVERSE_STATE' in SNAPSHOT


def _pdf_record():
    perf = {"1D": 1.0, "1M": 2.0, "3M": 3.0, "6M": 4.0, "YTD": 5.0, **{str(y): 6.0 for y in range(2025, 2005, -1)}}
    return {
        "id": "SIM-5918",
        "name": "Analyst Snapshot Test",
        "created_at_display_et": "Aug 28, 2026 06:00:00 PM EDT",
        "period": "10Y",
        "allocation_mode": "Equal split",
        "total_invested": 100000.0,
        "ending_value": 120000.0,
        "profit_loss": 20000.0,
        "total_return": 20.0,
        "instruments": [
            {
                "symbol": "AAPL", "type": "Stock", "name": "Apple Inc. Common Stock", "sector": "Technology",
                "analyst_rating": "Buy", "price_target_low": 215.0, "price_target_average": 324.45,
                "price_target_high": 400.0, "weight": 50.0, "allocated": 50000.0, "ending_value": 60000.0,
                "profit": 10000.0, "return_pct": 20.0, "performance": perf,
            },
            {
                "symbol": "SMH", "type": "ETF", "name": "VanEck Semiconductor ETF", "sector": "Semiconductors",
                "analyst_rating": "Not Rated", "price_target_low": None, "price_target_average": None,
                "price_target_high": None, "weight": 50.0, "allocated": 50000.0, "ending_value": 60000.0,
                "profit": 10000.0, "return_pct": 20.0, "performance": perf,
            },
        ],
    }


def test_pdf_first_page_has_identity_sector_rating_and_targets():
    for token in [
        "PORTFOLIO INSTRUMENTS / ANALYST SNAPSHOT", "SYMBOL / TYPE", "NAME", "SECTOR",
        "ANALYST RATING", "TARGET LOW", "TARGET AVG", "TARGET HIGH",
        '"analyst_rating"', '"price_target_low"', '"price_target_average"', '"price_target_high"',
    ]:
        assert token in PDF_SOURCE or token in APP
    pdf = build_portfolio_simulation_pdf(_pdf_record())
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 7000


def test_card_click_profit_contract_still_present_for_all_perf_cols():
    assert "render_card_profit_period_fragment" in APP
    assert "_period_profit_projection" in APP
    assert "on_click=_set_card_profit_period" in APP
    assert "for idx in range(0, len(PERF_COLS), 3)" in APP
