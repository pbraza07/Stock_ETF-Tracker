from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

def test_release_does_not_ship_live_simulation_library():
    assert not (BASE / "data" / "saved_portfolio_simulations.json").exists()
    assert (BASE / "data" / "saved_portfolio_simulations.bootstrap.json").exists()

def test_release_does_not_ship_live_generated_pdf_directory():
    # Existing PDFs belong to the deployed repository/runtime, not to release archives.
    generated = BASE / "data" / "generated_pdfs"
    assert not generated.exists() or not any(generated.glob("*.pdf"))

def test_pdf_storage_declares_upgrade_protected_paths():
    text = (BASE / "pdf_storage.py").read_text(encoding="utf-8")
    assert 'PDF_REPO_DIR = "data/generated_pdfs"' in text
    assert 'PROTECTED_SIMULATION_LIBRARY = "data/saved_portfolio_simulations.json"' in text
    assert "durable_pdf_storage_configured" in text

def test_upgrade_notes_name_both_protected_live_paths():
    text = (BASE / "IMPORTANT_UPGRADE_v5.9.43.md").read_text(encoding="utf-8")
    assert "data/saved_portfolio_simulations.json" in text
    assert "data/generated_pdfs/" in text
    assert "MARKETSCOPE_GITHUB_TOKEN" in text
