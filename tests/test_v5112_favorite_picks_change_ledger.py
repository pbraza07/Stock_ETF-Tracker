from __future__ import annotations

import json
import base64
from pathlib import Path

import pandas as pd

from favorite_picks_history import (
    empty_favorite_picks_ledger,
    favorite_change_history_frame,
    favorite_run_history_frame,
    merge_favorite_picks_ledgers,
    record_favorite_picks_run,
)
from persistence import persist_favorite_picks_history


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
PERSISTENCE = (ROOT / "persistence.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "update_market_snapshot.yml").read_text(encoding="utf-8")
UPDATER = (ROOT / "scripts" / "update_universe.py").read_text(encoding="utf-8")
DAILY = (ROOT / "scripts" / "update_favorite_picks_history.py").read_text(encoding="utf-8")


def pick_table(technology=("AAA", "BBB"), bbb_risk="Moderate") -> pd.DataFrame:
    rows = []
    for sector, symbols in (("Technology", technology), ("Health Care", ("CCC", "DDD"))):
        for rank, symbol in enumerate(symbols, start=1):
            risk = bbb_risk if symbol == "BBB" else "Low"
            rows.append({
                "Sector": sector,
                "Sector Rank": rank,
                "Symbol": symbol,
                "Name": f"Company {symbol}",
                "Risk Rating": risk,
                "Risk Score": 35.0 if risk == "Moderate" else (60.0 if risk == "High" else 18.0),
                "Favorite Score": 85.0 - rank,
                "Model Confidence": "High",
            })
    return pd.DataFrame(rows)


def test_release_version_and_bootstrap_history_contract():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.11.7"
    bootstrap = ROOT / "data" / "favorite_picks_history.bootstrap.json"
    assert bootstrap.exists()
    payload = json.loads(bootstrap.read_text(encoding="utf-8"))
    assert payload == empty_favorite_picks_ledger()
    assert not (ROOT / "data" / "favorite_picks_history.json").exists()


def test_initial_run_records_first_detected_event_for_every_pick():
    ledger, events = record_favorite_picks_run(
        empty_favorite_picks_ledger(),
        pick_table(),
        observed_at="2026-09-05T08:15:00-04:00",
        data_as_of="Sep 05, 2026 08:00 AM EDT",
        random_seed=20260904,
    )
    assert len(events) == 4
    assert {event["event_type"] for event in events} == {"Initial Favorite Pick"}
    assert all(event["first_detected_at_et"] == "2026-09-05T08:15:00-04:00" for event in events)
    assert len(ledger["runs"]) == 1
    assert ledger["current_picks"]["Technology"][0]["first_selected_at_et"] == "2026-09-05T08:15:00-04:00"


def test_unchanged_run_adds_a_run_but_no_event_and_preserves_first_dates():
    initial, _ = record_favorite_picks_run(
        empty_favorite_picks_ledger(), pick_table(), observed_at="2026-09-05T08:15:00-04:00"
    )
    second, events = record_favorite_picks_run(
        initial, pick_table(), observed_at="2026-09-06T08:15:00-04:00"
    )
    assert events == []
    assert len(second["events"]) == 4
    assert len(second["runs"]) == 2
    assert second["current_picks"]["Technology"][0]["first_selected_at_et"] == "2026-09-05T08:15:00-04:00"
    assert second["current_picks"]["Technology"][1]["risk_rating_first_detected_at_et"] == "2026-09-05T08:15:00-04:00"


def test_replacement_and_risk_change_are_logged_with_dropped_and_new_stock():
    initial, _ = record_favorite_picks_run(
        empty_favorite_picks_ledger(), pick_table(), observed_at="2026-09-05T08:15:00-04:00"
    )
    changed, events = record_favorite_picks_run(
        initial,
        pick_table(technology=("EEE", "BBB"), bbb_risk="High"),
        observed_at="2026-09-07T09:30:00-04:00",
    )
    replacements = [event for event in events if event["event_type"] == "Favorite Pick Replaced"]
    risk_changes = [event for event in events if event["event_type"] == "Favorite Risk Rating Changed"]
    assert len(replacements) == 1
    assert replacements[0]["sector"] == "Technology"
    assert replacements[0]["dropped_symbol"] == "AAA"
    assert replacements[0]["added_symbol"] == "EEE"
    assert replacements[0]["first_detected_at_et"] == "2026-09-07T09:30:00-04:00"
    assert len(risk_changes) == 1
    assert risk_changes[0]["symbol"] == "BBB"
    assert risk_changes[0]["previous_value"] == "Moderate"
    assert risk_changes[0]["new_value"] == "High"
    assert len(changed["events"]) == 6
    assert changed["events"][0]["first_detected_at_et"] == "2026-09-05T08:15:00-04:00"


def test_history_frames_show_all_events_and_previous_runs_newest_first():
    ledger, _ = record_favorite_picks_run(
        empty_favorite_picks_ledger(), pick_table(), observed_at="2026-09-05T08:15:00-04:00"
    )
    ledger, _ = record_favorite_picks_run(
        ledger, pick_table(("EEE", "BBB"), "High"), observed_at="2026-09-07T09:30:00-04:00"
    )
    changes = favorite_change_history_frame(ledger)
    runs = favorite_run_history_frame(ledger)
    replacement = changes.loc[changes["Change Type"].eq("Favorite Pick Replaced")].iloc[0]
    assert replacement["Dropped Pick"] == "AAA"
    assert replacement["Dropped Company"] == "Company AAA"
    assert replacement["New Pick"] == "EEE"
    assert replacement["New Company"] == "Company EEE"
    assert changes.iloc[0]["First Detected (ET)"].startswith("Sep 07, 2026")
    assert runs.iloc[0]["Run Date / Time (ET)"].startswith("Sep 07, 2026")


def test_merge_never_replaces_an_event_with_a_later_first_detected_date():
    event_id = "stable-event-id"
    early = {
        "event_id": event_id,
        "first_detected_at_et": "2026-09-05T08:00:00-04:00",
        "first_detected_display_et": "Sep 05, 2026 08:00:00 AM EDT",
        "event_type": "Favorite Pick Replaced",
        "sector": "Technology",
    }
    late = {**early, "first_detected_at_et": "2026-09-08T08:00:00-04:00"}
    merged = merge_favorite_picks_ledgers({"events": [late]}, {"events": [early]})
    assert merged["events"][0]["first_detected_at_et"] == early["first_detected_at_et"]


def test_persistence_writes_locally_and_uses_existing_github_token(tmp_path, monkeypatch):
    destination = tmp_path / "favorite_picks_history.json"
    ledger, _ = record_favorite_picks_run(
        empty_favorite_picks_ledger(), pick_table(), observed_at="2026-09-05T08:15:00-04:00"
    )
    captured = {}
    monkeypatch.setenv("MARKETSCOPE_GITHUB_TOKEN", "test-token")

    class Response:
        def __init__(self, status_code, payload=None):
            self.status_code = status_code
            self._payload = payload or {}

        def json(self):
            return self._payload

    monkeypatch.setattr("persistence.requests.get", lambda *args, **kwargs: Response(404))

    def fake_put(url, headers, json, timeout):
        captured.update(url=url, headers=headers, body=json)
        return Response(201)

    monkeypatch.setattr("persistence.requests.put", fake_put)
    ok, message = persist_favorite_picks_history(ledger, destination)
    assert ok is True
    assert "permanently" in message
    assert captured["url"].endswith("/contents/data/favorite_picks_history.json")
    assert captured["headers"]["Authorization"] == "Bearer test-token"
    saved_payload = json.loads(base64.b64decode(captured["body"]["content"]).decode("utf-8"))
    assert saved_payload["events"] == ledger["events"]
    assert json.loads(destination.read_text(encoding="utf-8"))["events"] == ledger["events"]


def test_persistence_merges_remote_events_before_saving(tmp_path, monkeypatch):
    destination = tmp_path / "favorite_picks_history.json"
    local, _ = record_favorite_picks_run(
        empty_favorite_picks_ledger(), pick_table(), observed_at="2026-09-06T08:15:00-04:00"
    )
    remote, _ = record_favorite_picks_run(
        empty_favorite_picks_ledger(), pick_table(("ZZZ", "BBB")), observed_at="2026-09-05T08:15:00-04:00"
    )
    remote_text = json.dumps(remote).encode("utf-8")
    monkeypatch.setenv("MARKETSCOPE_GITHUB_TOKEN", "test-token")

    class Response:
        def __init__(self, status_code, payload=None):
            self.status_code = status_code
            self._payload = payload or {}

        def json(self):
            return self._payload

    monkeypatch.setattr(
        "persistence.requests.get",
        lambda *args, **kwargs: Response(200, {"sha": "abc", "content": base64.b64encode(remote_text).decode("ascii")}),
    )
    captured = {}

    def fake_put(url, headers, json, timeout):
        captured["payload"] = __import__("json").loads(base64.b64decode(json["content"]).decode("utf-8"))
        return Response(200)

    monkeypatch.setattr("persistence.requests.put", fake_put)
    ok, _ = persist_favorite_picks_history(local, destination)
    assert ok is True
    assert len(captured["payload"]["events"]) == len(remote["events"]) + len(local["events"])
    assert captured["payload"]["last_run_at_et"] == local["last_run_at_et"]


def test_main_page_exposes_permanent_first_detected_change_trails():
    for token in (
        "Pick Fav Change Trail",
        "Favorite Picks Permanent Change Trail · All Time",
        "First Detected dates are never overwritten",
        "favorite_picks_permanent_change_history",
        "All-time stock and analyst archive",
        "nasdaq_all_time_change_history",
        "Favorite Risk Rating Changed",
        "load_favorite_picks_history",
        "persist_favorite_picks_history",
    ):
        assert token in APP


def test_daily_workflow_and_storage_preserve_the_ledger():
    assert 'FAVORITE_PICKS_HISTORY_PATH = "data/favorite_picks_history.json"' in PERSISTENCE
    assert "def load_remote_favorite_picks_history" in PERSISTENCE
    assert "def persist_favorite_picks_history" in PERSISTENCE
    assert "first_detected_at_et" in UPDATER
    assert "record_favorite_picks_run" in DAILY
    assert "Update daily Favorite Picks change ledger" in WORKFLOW
    assert "continue-on-error: true" in WORKFLOW
    assert "steps.favorite-picks-history.outcome == 'success'" in WORKFLOW
    assert "data/favorite_picks_history.json" in WORKFLOW
