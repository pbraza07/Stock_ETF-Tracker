from pathlib import Path

from portfolio_simulations import build_portfolio_simulation_pdf

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
YAHOO = (ROOT / "providers" / "yahoo.py").read_text(encoding="utf-8")


def _enriched_record():
    performance = {
        "1D": 1.2, "1M": 2.3, "3M": 4.5, "6M": 8.1, "YTD": 11.5,
        "2025": 20.0, "2024": 15.0, "2023": -5.0, "2022": -10.0, "2021": 30.0,
        "2020": 25.0, "2019": 18.0, "2018": -2.0, "2017": 12.0, "2016": 9.0,
    }
    return {
        "id": "SIM-V596",
        "name": "Analytics Test",
        "created_at_display_et": "Aug 28, 2026 09:00 AM EDT",
        "created_date": "2026-08-28",
        "period": "10Y",
        "allocation_mode": "Custom %",
        "total_invested": 200000,
        "ending_value": 300000,
        "profit_loss": 100000,
        "total_return": 50,
        "instruments": [{
            "symbol": "NVDA", "type": "Stock", "sector": "Technology", "industry": "Semiconductors",
            "weight": 50, "allocated": 100000, "ending_value": 170000, "profit": 70000, "return_pct": 70,
            "cagr_10y_pct": 18.25, "positive_years": 7, "available_years": 10,
            "worst_year": "2022", "worst_year_pct": -10.0, "best_year": "2021", "best_year_pct": 30.0,
            "regular_yield_pct": 0.04, "est_annual_dividend": 40.0, "performance": performance,
        }],
    }


def test_release_596():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.6"


def test_portfolio_information_table_contract():
    for label in [
        "PORTFOLIO INFORMATION & PERFORMANCE TABLE", "Industry", "Stock", "Allocation",
        "10-year CAGR", "Positive years", "Worst year and %", "Best year and %",
        "Regular yield", "Est. annual dividend",
    ]:
        assert label in APP
    assert "for metric in PERF_COLS" in APP
    assert "_ten_year_stats" in APP
    assert "_portfolio_analytics_payload" in APP


def test_saved_records_include_analytics_and_performance():
    required = [
        '"cagr_10y_pct"', '"positive_years"', '"worst_year"', '"worst_year_pct"',
        '"best_year"', '"best_year_pct"', '"regular_yield_pct"',
        '"est_annual_dividend"', '"performance"',
    ]
    save_section = APP.split("if save_simulation_clicked and portfolio_save_ready:", 1)[1]
    for token in required:
        assert token in save_section


def test_yahoo_income_metrics_are_on_demand():
    assert "def get_income_metrics(" in YAHOO
    assert "def get_income_metrics_many(" in YAHOO
    assert "trailingAnnualDividendRate" in YAHOO
    assert "ticker.dividends" in YAHOO
    assert "cached_income_metrics" in APP


def test_enriched_pdf_contains_supplemental_tables():
    pdf = build_portfolio_simulation_pdf(_enriched_record())
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 5000
    source = (ROOT / "portfolio_simulations.py").read_text(encoding="utf-8")
    assert "PORTFOLIO INFORMATION TABLE" in source
    assert "TIMEFRAME PERFORMANCE TABLE" in source
    assert "EST. ANNUAL DIV." in source
