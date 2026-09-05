from pathlib import Path

from portfolio_simulations import _combined_portfolio_metrics, build_portfolio_simulation_pdf

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "portfolio_simulations.py").read_text(encoding="utf-8")


def _record():
    years = {
        "2025": 10.0, "2024": 20.0, "2023": 30.0, "2022": -10.0, "2021": 15.0,
        "2020": 5.0, "2019": 12.0, "2018": -4.0, "2017": 8.0, "2016": 6.0,
    }
    p1 = {"1D": 1.0, "1M": 2.0, "3M": 3.0, "6M": 4.0, "YTD": 5.0, **years}
    p2 = {key: value + 10.0 for key, value in p1.items()}
    return {
        "id": "SIM-V597", "name": "Combined Test", "period": "10Y", "allocation_mode": "Custom %",
        "created_at_display_et": "Aug 28, 2026 10:00 AM EDT", "total_invested": 200000,
        "ending_value": 300000, "profit_loss": 100000, "total_return": 50,
        "instruments": [
            {"symbol": "AAA", "weight": 25, "allocated": 50000, "regular_yield_pct": 2.0,
             "est_annual_dividend": 1000, "performance": p1},
            {"symbol": "BBB", "weight": 75, "allocated": 150000, "regular_yield_pct": 4.0,
             "est_annual_dividend": 6000, "performance": p2},
        ],
    }


def test_release_597():
    assert tuple(map(int, (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip().split("."))) >= (5, 9, 8)


def test_combined_portfolio_weighting_and_income():
    combined = _combined_portfolio_metrics(_record())
    # 25% * 1% + 75% * 11% = 8.5%
    assert round(combined["performance"]["1D"], 4) == 8.5
    assert round(combined["regular_yield_pct"], 4) == 3.5
    assert round(combined["est_annual_dividend"], 2) == 7000.00
    assert combined["available_years"] == 10
    assert combined["positive_years"] >= 8
    assert combined["cagr_10y_pct"] is not None


def test_first_page_contains_requested_combined_tables():
    for token in [
        "COMBINED PORTFOLIO PERFORMANCE", "10Y CAGR", "POS YEARS", "WORST YEAR", "BEST YEAR",
        "REG. YIELD", "EST. ANNUAL DIV.", "COMBINED TIMEFRAME PERFORMANCE",
        '"1D", "1M", "3M", "6M", "YTD"',
        "completed annual returns are dynamically paginated into legible timeframe bands",
    ]:
        assert token in SOURCE
    assert 'saved_years[:5]' in SOURCE
    assert 'remaining_years = saved_years[5:]' in SOURCE
    assert 'for start_index in range(0, len(remaining_years), 10)' in SOURCE
    assert 'OLDER COMPLETED CALENDAR YEARS' in SOURCE
    pdf = build_portfolio_simulation_pdf(_record())
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 6000
