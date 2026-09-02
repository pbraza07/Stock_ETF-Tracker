from __future__ import annotations

import importlib.util
import io
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "update_market_snapshot.yml").read_text(encoding="utf-8")
UPDATE = (ROOT / "scripts" / "update_snapshot.py").read_text(encoding="utf-8")
PDF = (ROOT / "portfolio_simulations.py").read_text(encoding="utf-8")

spec = importlib.util.spec_from_file_location("verify_annual_returns", ROOT / "scripts" / "verify_annual_returns.py")
VERIFY = importlib.util.module_from_spec(spec)
spec.loader.exec_module(VERIFY)


def _make_archive(path: Path) -> Path:
    # Year-end closes imply +10% for 2001 and +10% for 2002.
    content = (
        "<TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>\n"
        "TEST.US,D,20001229,000000,100,100,100,100,1,0\n"
        "TEST.US,D,20011231,000000,110,110,110,110,1,0\n"
        "TEST.US,D,20021231,000000,121,121,121,121,1,0\n"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("data/daily/us/nasdaq stocks/1/test.us.txt", content)
    return path


def test_release_version_5956():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.79"


def test_verifier_compares_actual_year_end_returns(tmp_path):
    archive = _make_archive(tmp_path / "stooq.zip")
    snapshot = pd.DataFrame([{"Symbol": "TEST", "2001": 10.0, "2002": 10.0}])
    out = VERIFY.verify_snapshot(snapshot, archive, tolerance_pp=0.25)
    row = out.iloc[0]
    assert row["History Verification"] == "Verified"
    assert row["Verification Coverage"] == "2/2"
    assert int(row["Verified Years"]) == 2
    assert int(row["Verification Discrepancies"]) == 0
    assert float(row["Max Verification Diff (pp)"]) < 0.0001


def test_verifier_flags_difference_over_point25(tmp_path):
    archive = _make_archive(tmp_path / "stooq.zip")
    snapshot = pd.DataFrame([{"Symbol": "TEST", "2001": 10.40, "2002": 10.0}])
    out = VERIFY.verify_snapshot(snapshot, archive, tolerance_pp=0.25)
    row = out.iloc[0]
    assert row["History Verification"] == "Review"
    assert int(row["Verification Discrepancies"]) == 1
    assert "2001:" in row["Verification Exceptions"]
    assert float(row["Max Verification Diff (pp)"]) >= 0.39


def test_workflow_runs_independent_verification_before_persistence():
    verify_pos = WORKFLOW.index("Cross-check dynamic annual returns against Stooq")
    persist_pos = WORKFLOW.index("Persist verified dynamic market snapshot and monthly history")
    assert verify_pos < persist_pos
    assert "actions/cache@v4" in WORKFLOW
    assert "MARKETSCOPE_VERIFICATION_TOLERANCE_PP" in WORKFLOW
    assert "0.25" in WORKFLOW


def test_snapshot_preserves_previous_verification_metadata():
    for col in [
        "History Verification",
        "Verification Coverage",
        "Verification Discrepancies",
        "Max Verification Diff (pp)",
        "Verification Exceptions",
        "Verification Source",
        "Verification Updated ET",
    ]:
        assert col in UPDATE


def test_market_table_exposes_verification_fields():
    assert '"History Verification"' in APP
    assert '"Verification Coverage"' in APP
    assert '"Verification Discrepancies"' in APP
    assert '"Max Verification Diff (pp)"' in APP
    assert '"Verification Exceptions"' in APP
    assert "History Check compares Yahoo/yfinance annual returns with independent Stooq" in APP


def test_cards_show_history_verification_badge():
    assert "def _history_verification_badge_html" in APP
    assert "_history_verification_badge_html(row)" in APP
    assert "History {escape(status)}" in APP


def test_pdf_carries_history_check():
    assert '"HISTORY CHECK"' in PDF
    assert "history_verification" in PDF
    assert "independent Stooq bulk historical Close" in PDF


def test_secondary_source_does_not_replace_primary_return():
    source = (ROOT / "scripts" / "verify_annual_returns.py").read_text(encoding="utf-8")
    assert "snapshot.at[idx, col] = value" in source
    # Verifier only writes verification fields; no assignment to year columns.
    assert 'snapshot.at[idx, year]' not in source
