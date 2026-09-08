from io import BytesIO
from pathlib import Path

import pandas as pd
from pypdf import PdfReader

from future_projection import build_pdf_export
from top12_exports import build_top12_pdf


def _assert_stock_projection_layout(pdf_bytes: bytes, expected_title: str):
    assert pdf_bytes.startswith(b"%PDF")
    reader = PdfReader(BytesIO(pdf_bytes))
    assert reader.pages
    for page in reader.pages:
        assert float(page.mediabox.width) > float(page.mediabox.height)
        text = page.extract_text() or ""
        assert "MarketScope v5.11.11" in text
        assert "Page " in text
    first_page_text = reader.pages[0].extract_text() or ""
    assert expected_title in first_page_text


def test_future_projection_pdf_uses_stock_projection_layout():
    result = {
        "metadata": {
            "data_as_of": "2026-09-08",
            "model_as_of": "2026-09-08",
            "simulation_count": 5000,
            "random_seed": 42,
            "forecast_start_year": 2027,
            "forecast_end_year": 2031,
            "live_data_status": "Latest available",
            "projection_calibration_score": 75,
            "projection_confidence": "Medium",
        },
        "inputs": {
            "starting_investment": 100000,
            "withdrawal_frequency": "Annual",
            "withdrawal_timing": "Year end",
            "annual_withdrawal": 0,
            "monthly_withdrawal": 0,
            "strategy": "Both",
            "projection_profile": "Auto",
            "rebalancing_frequency": "Annual",
            "annual_management_fee": 0,
            "holdings": ["AAPL"],
            "allocations": {"AAPL": 100.0},
        },
        "current_market_state": {},
        "strategies": {},
        "comparison": pd.DataFrame(),
        "warnings": [],
        "limitations": ["Probabilistic output."],
        "model_assumptions": pd.DataFrame(),
    }
    _assert_stock_projection_layout(
        build_pdf_export(result), "MarketScope Future Projection"
    )


def test_both_top12_pdfs_use_stock_projection_layout():
    base_rows = []
    for rank in range(1, 13):
        base_rows.append({
            "Rank": rank,
            "Symbol": f"S{rank:02d}",
            "Name": f"Company {rank}",
            "Sector": f"Sector {(rank - 1) // 4 + 1}",
            "Recession Score": 90 - rank,
            "Max Profit Score": 90 - rank,
            "Data Confidence": "HIGH",
            "Maximum Drawdown %": -10 - rank,
            "Recovery Periods": rank,
            "Recovery Basis": "Monthly",
            "Why Selected": "Calculated evidence supports selection.",
            **{f"Bear P{q} Future Return %": q / 10 for q in (10, 25, 50, 75, 90)},
            **{f"P{q} Future Return %": q / 10 for q in (10, 25, 50, 75, 90)},
        })
    table = pd.DataFrame(base_rows)
    result = {
        "metadata": {"Ranking Generated": "2026-09-08", "Eligible Stocks": 12},
        "all_scores": table.copy(),
        "warnings": [],
    }
    _assert_stock_projection_layout(
        build_top12_pdf("Recession", table, result),
        "Top 12 Recession-Resilient Stocks",
    )
    _assert_stock_projection_layout(
        build_top12_pdf("Max Profit", table, result),
        "Top 12 Max-Profit High-Performance Stocks",
    )


def test_saved_pdf_contract_forces_legacy_artifacts_to_rebuild():
    app_source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert app_source.count("unified PDF layout v5.11.11") >= 2
