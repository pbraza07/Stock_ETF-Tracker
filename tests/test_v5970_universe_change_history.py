from __future__ import annotations

import ast
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
PERSISTENCE = (ROOT / "persistence.py").read_text(encoding="utf-8")
UPDATER = (ROOT / "scripts" / "update_universe.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "update_market_snapshot.yml").read_text(encoding="utf-8")


def test_release_version_5970():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.74"
    assert "v5.9.74" in APP


def test_append_only_history_file_is_packaged():
    path = ROOT / "data" / "universe_change_history.json"
    assert path.exists()
    assert isinstance(json.loads(path.read_text(encoding="utf-8")), list)


def _updater_helpers():
    tree = ast.parse(UPDATER)
    names = {
        "_history_event_key",
        "_append_history_events",
        "_metadata_events",
    }
    return [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]


def test_updater_never_prunes_old_history_and_deduplicates():
    ns = {}
    exec(compile(ast.Module(body=_updater_helpers(), type_ignores=[]), "update_universe.py", "exec"), ns)

    old = [{
        "occurred_at_et": "2025-01-01T10:00:00-05:00",
        "change_type": "Stock Added",
        "symbol": "OLD",
        "from": "Outside >$100B universe",
        "to": "Included >$100B universe",
    }]
    new = [{
        "occurred_at_et": "2026-09-02T11:25:00-04:00",
        "change_type": "Stock Removed",
        "symbol": "AEM",
        "from": "Included >$100B universe",
        "to": "Outside >$100B universe",
    }]
    merged = ns["_append_history_events"](old, new + new)
    assert len(merged) == 2
    assert any(event["symbol"] == "OLD" for event in merged)
    assert sum(event["symbol"] == "AEM" for event in merged) == 1


def test_metadata_converts_added_removed_and_rating_changes_to_events():
    ns = {}
    exec(compile(ast.Module(body=_updater_helpers(), type_ignores=[]), "update_universe.py", "exec"), ns)

    metadata = {
        "refreshed_at_et": "2026-09-02T11:25:00-04:00",
        "refreshed_at_display_et": "Sep 02, 2026 11:25:00 AM EDT",
        "source": "Nasdaq Stock Screener",
        "added_symbols": ["AAA"],
        "removed_symbols": ["AEM"],
        "analyst_rating_changes": [{
            "symbol": "XYZ",
            "name": "XYZ Corp",
            "from": "Hold",
            "to": "Buy",
        }],
    }
    events = ns["_metadata_events"](metadata, {"AAA": {"Name": "AAA Corp"}, "AEM": {"Name": "Agnico Eagle"}})
    assert [event["change_type"] for event in events] == ["Stock Added", "Stock Removed", "Analyst Rating"]
    assert events[0]["name"] == "AAA Corp"
    assert events[1]["symbol"] == "AEM"
    assert events[2]["from"] == "Hold"
    assert events[2]["to"] == "Buy"


def test_updater_migrates_previous_metadata_before_writing_current_events():
    assert "prior_universe_meta = _read_json(UNIVERSE_META_OUT, {})" in UPDATER
    prior_pos = UPDATER.index("_metadata_events(prior_universe_meta")
    current_pos = UPDATER.index("_metadata_events(universe_meta")
    write_pos = UPDATER.index("UNIVERSE_HISTORY_OUT.write_text")
    assert prior_pos < current_pos < write_pos
    assert "Historical universe/rating change events retained" in UPDATER


def _app_history_helpers():
    tree = ast.parse(APP)
    names = {
        "_universe_history_event_key",
        "_merge_universe_change_history",
        "_current_metadata_change_events",
        "_six_month_universe_history_frame",
    }
    return [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]


def test_six_month_view_filters_display_only_not_storage():
    ns = {"pd": pd}
    exec(compile(ast.Module(body=_app_history_helpers(), type_ignores=[]), "app.py", "exec"), ns)
    history = [
        {
            "occurred_at_et": "2025-12-01T10:00:00-05:00",
            "occurred_at_display_et": "Dec 01, 2025 10:00:00 AM EST",
            "change_type": "Stock Added",
            "symbol": "OLD",
            "name": "Old Corp",
            "from": "Outside",
            "to": "Inside",
            "source": "Nasdaq",
        },
        {
            "occurred_at_et": "2026-08-15T10:00:00-04:00",
            "occurred_at_display_et": "Aug 15, 2026 10:00:00 AM EDT",
            "change_type": "Analyst Rating",
            "symbol": "NEW",
            "name": "New Corp",
            "from": "Hold",
            "to": "Buy",
            "source": "Nasdaq",
        },
    ]
    frame = ns["_six_month_universe_history_frame"](
        history,
        as_of="2026-09-02T12:00:00-04:00",
    )
    assert len(history) == 2  # source collection remains untouched
    assert frame["Symbol"].tolist() == ["NEW"]
    assert frame["Change Type"].tolist() == ["Analyst Rating"]


def test_current_metadata_bridge_preserves_latest_pre_upgrade_change():
    ns = {"pd": pd}
    exec(compile(ast.Module(body=_app_history_helpers(), type_ignores=[]), "app.py", "exec"), ns)
    metadata = {
        "refreshed_at_et": "2026-09-02T11:25:00-04:00",
        "refreshed_at_display_et": "Sep 02, 2026 11:25:00 AM EDT",
        "removed_symbols": ["AEM"],
        "analyst_rating_changes": [],
    }
    events = ns["_current_metadata_change_events"](metadata)
    assert len(events) == 1
    assert events[0]["change_type"] == "Stock Removed"
    assert events[0]["symbol"] == "AEM"


def test_market_navigator_has_requested_change_history_button_and_table():
    for token in [
        "🕘 6-Month Change History",
        "toggle_universe_change_history",
        "Nasdaq Universe & Analyst Change History · Last 6 Months",
        "Total changes",
        "Stocks added",
        "Stocks removed",
        "Rating changes",
        "nasdaq_six_month_change_history",
    ]:
        assert token in APP


def test_history_view_explicitly_says_old_records_are_retained():
    assert "underlying historical log is never pruned" in APP
    assert "Older events remain permanently stored for historical purposes." in APP


def test_manual_refresh_starts_from_remote_history_and_persists_updated_history():
    assert "remote_history = load_remote_universe_change_history(timeout=12)" in APP
    assert 'history_path = BASE_DIR / "data" / "universe_change_history.json"' in APP
    assert "generated_history" in APP
    assert "persist_universe_refresh(" in APP


def test_persistence_supports_durable_change_history():
    assert 'UNIVERSE_CHANGE_HISTORY_PATH = "data/universe_change_history.json"' in PERSISTENCE
    assert "def load_remote_universe_change_history" in PERSISTENCE
    assert "history_path: Optional[Path] = None" in PERSISTENCE
    assert "UNIVERSE_CHANGE_HISTORY_PATH" in PERSISTENCE
    assert "manual Nasdaq universe change history" in PERSISTENCE


def test_workflow_persists_history_immediately_and_ignores_generated_commits():
    assert "'data/universe_change_history.json'" in WORKFLOW
    early = WORKFLOW.index("Persist Nasdaq universe refresh immediately")
    historical = WORKFLOW.index("data/universe_change_history.json", early)
    snapshot = WORKFLOW.index("Build dynamic annual returns", early)
    assert early < historical < snapshot


def test_pdf_contract_bumped_to_v28():
    marker = 'MarketScope Portfolio Split Simulator v32 - v5.9.74 annual reset inside withdrawal tabs + annual reset withdrawal factor + annual positive years + display-mode searchable dropdowns + six-month universe change history + saved-card inline withdrawal summary + PDF withdrawal summary + Market Table target transcription + required instrument market data on page 1'
    assert APP.count(marker) >= 2
