from __future__ import annotations

import json
from pathlib import Path

import persistence

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
PERSISTENCE = (ROOT / "persistence.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "update_market_snapshot.yml").read_text(encoding="utf-8")


def test_release_version_5965():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.67"
    assert "v5.9.66" in APP


def test_pending_copy_refers_to_first_success_not_only_schedule():
    assert 'universe_refreshed = "Pending first successful universe refresh"' in APP
    assert 'Pending first scheduled refresh' not in APP


def test_market_navigator_has_manual_universe_refresh_button():
    assert '"↻ Refresh Nasdaq Universe Now"' in APP
    assert 'key="refresh_nasdaq_universe_now"' in APP
    assert "def _run_manual_universe_refresh" in APP
    assert 'scripts" / "update_universe.py"' in APP
    assert "timeout=300" in APP


def test_manual_button_refreshes_membership_metadata_not_fake_snapshot_timestamp():
    assert "persist_universe_refresh(generated_universe, generated_metadata)" in APP
    assert '"stock_count"' in APP
    assert '"added_count"' in APP
    assert '"removed_count"' in APP
    assert "load_universe_metadata.clear()" in APP


def test_manual_universe_persistence_uses_existing_contents_token(monkeypatch, tmp_path):
    universe = tmp_path / "default_universe.csv"
    metadata = tmp_path / "universe_metadata.json"
    universe.write_text("Symbol,Type\\nAAPL,Stock\\n", encoding="utf-8")
    metadata.write_text(json.dumps({"refreshed_at_display_et": "Sep 02, 2026 09:00:00 AM EDT"}), encoding="utf-8")

    calls = []
    monkeypatch.setenv("MARKETSCOPE_GITHUB_TOKEN", "test-token")
    monkeypatch.setattr(
        persistence,
        "_put_text_file",
        lambda path, text, message, token: (calls.append((path, text, token)) or (True, "ok")),
    )

    ok, message = persistence.persist_universe_refresh(universe, metadata)
    assert ok is True
    assert "saved permanently" in message.lower()
    assert [call[0] for call in calls] == ["data/default_universe.csv", "data/universe_metadata.json"]
    assert all(call[2] == "test-token" for call in calls)


def test_manual_universe_refresh_still_works_locally_without_token(monkeypatch, tmp_path):
    universe = tmp_path / "default_universe.csv"
    metadata = tmp_path / "universe_metadata.json"
    universe.write_text("Symbol,Type\\nAAPL,Stock\\n", encoding="utf-8")
    metadata.write_text("{}", encoding="utf-8")
    monkeypatch.delenv("MARKETSCOPE_GITHUB_TOKEN", raising=False)
    ok, message = persistence.persist_universe_refresh(universe, metadata)
    assert ok is False
    assert "current Render server" in message
    assert "MARKETSCOPE_GITHUB_TOKEN" in message


def test_scheduled_workflow_persists_universe_before_long_history_work():
    refresh_pos = WORKFLOW.index("Refresh Nasdaq >$100B universe and analyst ratings")
    persist_pos = WORKFLOW.index("Persist Nasdaq universe refresh immediately")
    history_pos = WORKFLOW.index("Build dynamic annual returns and matching actual monthly history")
    assert refresh_pos < persist_pos < history_pos
    early = WORKFLOW[persist_pos:history_pos]
    assert "data/default_universe.csv" in early
    assert "data/universe_metadata.json" in early


def test_pdf_contract_bumped_to_v24():
    marker = "MarketScope Portfolio Split Simulator v25 - v5.9.66 end-to-end analyst target restore + manual universe refresh + responsive withdrawal KPI layout + required instrument market data on page 1"
    assert APP.count(marker) >= 2
