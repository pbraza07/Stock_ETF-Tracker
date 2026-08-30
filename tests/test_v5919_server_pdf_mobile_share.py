from __future__ import annotations

from pathlib import Path

from pdf_storage import (
    artifact_name,
    download_filename,
    load_pdf_artifact,
    pdf_viewer_url,
    persist_pdf_artifact,
    static_pdf_path,
)
from portfolio_simulations import build_portfolio_simulation_pdf


def _record():
    return {
        "id": "SIM-20260829-TEST",
        "name": "Family Growth Portfolio",
        "created_date": "2026-08-29",
        "created_at_display_et": "Aug 29, 2026 07:00:00 AM EDT",
        "period": "10Y",
        "allocation_mode": "Equal split",
        "total_invested": 200000.0,
        "ending_value": 250000.0,
        "profit_loss": 50000.0,
        "total_return": 25.0,
        "instrument_count": 1,
        "instruments": [
            {
                "symbol": "NVDA",
                "name": "NVIDIA Corporation",
                "type": "Stock",
                "sector": "Technology",
                "weight": 100.0,
                "allocated": 200000.0,
                "ending_value": 250000.0,
                "profit": 50000.0,
                "return_pct": 25.0,
                "performance": {},
            }
        ],
    }


def test_real_pdf_is_saved_to_server_static_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("MARKETSCOPE_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("MARKETSCOPE_PDF_PERSIST_DIR", raising=False)
    record = _record()
    pdf = build_portfolio_simulation_pdf(record)
    ok, message, metadata = persist_pdf_artifact(pdf, record, tmp_path, "test PDF save")
    assert ok is False  # no GitHub token, but local server save must still succeed
    assert "real file on the MarketScope server" in message
    record.update(metadata)
    stored = static_pdf_path(tmp_path, record)
    assert stored.exists()
    assert stored.read_bytes().startswith(b"%PDF")
    assert metadata["pdf_storage"] == "server"


def test_load_uses_saved_server_pdf_without_rebuilding(tmp_path, monkeypatch):
    monkeypatch.delenv("MARKETSCOPE_GITHUB_TOKEN", raising=False)
    record = _record()
    pdf = build_portfolio_simulation_pdf(record)
    _, _, metadata = persist_pdf_artifact(pdf, record, tmp_path, "test PDF save")
    record.update(metadata)

    def should_not_run(_record):
        raise AssertionError("builder should not run when stored PDF exists")

    loaded = load_pdf_artifact(record, tmp_path, builder=should_not_run)
    assert loaded == pdf


def test_mobile_viewer_url_and_names_are_safe():
    record = _record()
    assert artifact_name(record).endswith(".pdf")
    assert download_filename(record) == "MarketScope_Family_Growth_Portfolio_2026-08-29.pdf"
    url = pdf_viewer_url(record)
    assert url.startswith("/app/static/pdf_viewer.html?file=")
    assert "name=MarketScope_Family_Growth_Portfolio_2026-08-29.pdf" in url


def test_streamlit_static_pdf_and_mobile_share_contract():
    root = Path(__file__).resolve().parents[1]
    config = (root / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    app = (root / "app.py").read_text(encoding="utf-8")
    viewer = (root / "static" / "pdf_viewer.html").read_text(encoding="utf-8")
    assert "enableStaticServing = true" in config
    assert "Open / Share PDF" in app
    assert "persist_pdf_artifact" in app
    assert "delete_pdf_artifact" in app
    assert "navigator.share" in viewer
    assert "new File([blob]" in viewer
    assert "Mail, Messages" in viewer
    assert "Back to MarketScope" in viewer
    assert "window.opener.focus()" in viewer
