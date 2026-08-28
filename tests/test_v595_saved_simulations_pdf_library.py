from __future__ import annotations

import json
from pathlib import Path

from portfolio_simulations import (
    add_simulation,
    build_portfolio_simulation_pdf,
    delete_simulation,
    load_saved_simulations,
    persist_saved_simulations,
    safe_filename,
)


def _record():
    return {
        "id": "SIM-TEST-001",
        "name": "Test Portfolio",
        "created_at_et": "2026-08-28T08:30:00-04:00",
        "created_at_display_et": "Aug 28, 2026 08:30:00 AM EDT",
        "created_date": "2026-08-28",
        "period": "5Y",
        "allocation_mode": "Equal split",
        "total_invested": 200000.0,
        "ending_value": 225000.0,
        "profit_loss": 25000.0,
        "total_return": 12.5,
        "instrument_count": 2,
        "instruments": [
            {
                "symbol": "NVDA",
                "type": "Stock",
                "sector": "Technology",
                "weight": 50.0,
                "allocated": 100000.0,
                "ending_value": 130000.0,
                "profit": 30000.0,
                "return_pct": 30.0,
            },
            {
                "symbol": "SMH",
                "type": "ETF",
                "sector": "Semiconductors",
                "weight": 50.0,
                "allocated": 100000.0,
                "ending_value": 95000.0,
                "profit": -5000.0,
                "return_pct": -5.0,
            },
        ],
    }


def test_pdf_generation_and_filename():
    record = _record()
    pdf = build_portfolio_simulation_pdf(record)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 2000
    filename = safe_filename(record)
    assert filename.endswith(".pdf")
    assert "Test_Portfolio" in filename


def test_add_and_delete_simulation():
    record = _record()
    records = add_simulation([], record)
    assert len(records) == 1
    assert records[0]["id"] == record["id"]
    assert delete_simulation(records, record["id"]) == []


def test_local_persistence_without_token(tmp_path, monkeypatch):
    monkeypatch.delenv("MARKETSCOPE_GITHUB_TOKEN", raising=False)
    ok, message = persist_saved_simulations([_record()], tmp_path, "test save")
    assert ok is False
    assert "current app session/server" in message
    live = tmp_path / "saved_portfolio_simulations.json"
    assert live.exists()
    loaded = load_saved_simulations(tmp_path)
    assert loaded and loaded[0]["id"] == "SIM-TEST-001"


def test_upgrade_package_uses_bootstrap_not_live_library():
    base = Path(__file__).resolve().parents[1]
    assert (base / "data" / "saved_portfolio_simulations.bootstrap.json").exists()
    # A release package should not ship a live library that could overwrite user data.
    assert not (base / "data" / "saved_portfolio_simulations.json").exists()


def test_app_contract_and_reportlab_dependency():
    base = Path(__file__).resolve().parents[1]
    app = (base / "app.py").read_text(encoding="utf-8")
    requirements = (base / "requirements.txt").read_text(encoding="utf-8")
    assert "Save PDF to Library" in app
    assert "Saved Simulations" in app
    assert "Download PDF" in app
    assert "Confirm Delete" in app
    assert "build_portfolio_simulation_pdf" in app
    assert "reportlab" in requirements
