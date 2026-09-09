from pathlib import Path

from portfolio_simulations import _history_verification_status


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
PDF = (ROOT / "portfolio_simulations.py").read_text(encoding="utf-8")


def test_release_version():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.11.18"


def test_pending_is_normalized_to_unavailable():
    for value in (None, "", "Pending", "pending", "nan", "—"):
        assert _history_verification_status(value) == "Unavailable"
    assert _history_verification_status("Verified") == "Verified"
    assert _history_verification_status("Partial") == "Partial"
    assert _history_verification_status("Review") == "Review"


def test_card_badge_and_saved_pdf_never_default_to_pending():
    assert "History Check: " in APP
    assert '"pending":' not in APP
    assert 'or "Pending"' not in APP
    assert 'else "Pending"' not in APP
    assert 'or "Pending"' not in PDF


def test_snapshot_normalization_repairs_old_pending_values():
    assert 'df["History Verification"].map(_normalized_history_verification)' in APP
    assert '"pending"' in APP
