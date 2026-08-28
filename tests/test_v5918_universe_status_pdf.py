from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import scripts.update_universe as update_universe
from portfolio_simulations import build_portfolio_simulation_pdf

ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = (ROOT / "app.py").read_text(encoding="utf-8")
PDF_SOURCE = (ROOT / "portfolio_simulations.py").read_text(encoding="utf-8")
WORKFLOW_SOURCE = (ROOT / ".github/workflows/update_market_snapshot.yml").read_text(encoding="utf-8")


def test_release_5918_and_status_contract():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.18"
    assert "Nasdaq Universe Last Refreshed:" in APP_SOURCE
    assert "Stocks Added / Removed Today:" in APP_SOURCE
    assert "data/universe_metadata.json" in WORKFLOW_SOURCE


def test_universe_metadata_tracks_added_removed_today(tmp_path, monkeypatch):
    monkeypatch.setattr(update_universe, "UNIVERSE_META_OUT", tmp_path / "universe_metadata.json")
    monkeypatch.setattr(
        update_universe,
        "now_et",
        lambda: datetime(2026, 8, 28, 18, 0, 0, tzinfo=ZoneInfo("America/New_York")),
    )
    previous = pd.DataFrame([
        {"Symbol": "AAA", "Type": "Stock"},
        {"Symbol": "BBB", "Type": "Stock"},
        {"Symbol": "QQQ", "Type": "ETF"},
    ])
    current = pd.DataFrame([
        {"Symbol": "BBB", "Type": "Stock"},
        {"Symbol": "CCC", "Type": "Stock"},
    ])
    payload = update_universe._write_universe_metadata(previous, current, 213)
    assert payload["stocks_added_today"] == ["CCC"]
    assert payload["stocks_removed_today"] == ["AAA"]
    assert payload["stocks_added_today_count"] == 1
    assert payload["stocks_removed_today_count"] == 1
    assert "Aug 28, 2026 06:00:00 PM EDT" == payload["refreshed_at_display_et"]


def test_pdf_first_page_contains_instrument_analyst_snapshot(tmp_path):
    performance = {
        "1D": 1.0, "1M": 2.0, "3M": 3.0, "6M": 4.0, "YTD": 5.0,
        **{str(year): 8.0 for year in range(2025, 2005, -1)},
    }
    record = {
        "id": "SIM-V5918",
        "name": "Analyst Snapshot Test",
        "period": "10Y",
        "allocation_mode": "Equal split",
        "created_at_display_et": "Aug 28, 2026 03:00 PM EDT",
        "total_invested": 100000,
        "ending_value": 112000,
        "profit_loss": 12000,
        "total_return": 12,
        "instruments": [
            {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "type": "Stock",
                "sector": "Technology",
                "analyst_rating": "Buy",
                "price_target_low": 210.0,
                "price_target_average": 260.0,
                "price_target_high": 300.0,
                "weight": 100,
                "allocated": 100000,
                "ending_value": 112000,
                "profit": 12000,
                "return_pct": 12,
                "performance": performance,
            }
        ],
    }
    pdf = build_portfolio_simulation_pdf(record)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 6000
    for token in [
        "PORTFOLIO INSTRUMENT / ANALYST SNAPSHOT",
        "analyst_rating", "price_target_low", "price_target_average", "price_target_high",
        "TARGET LOW", "TARGET AVG", "TARGET HIGH",
    ]:
        assert token in PDF_SOURCE
