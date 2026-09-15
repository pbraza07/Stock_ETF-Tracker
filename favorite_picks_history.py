"""Append-only Favorite Picks run and change history.

The ledger stores the first detected timestamp on each event and never edits or
prunes an existing event. Current state is kept separately so a new run can be
compared with the last durable sector selections.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
from zoneinfo import ZoneInfo

import pandas as pd


ET = ZoneInfo("America/New_York")
SCHEMA_VERSION = 1


def empty_favorite_picks_ledger() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "last_run_at_et": "",
        "current_picks": {},
        "events": [],
        "runs": [],
    }


def _timestamp(value=None) -> tuple[str, str]:
    if value is None:
        stamp = datetime.now(ET)
    else:
        stamp = pd.Timestamp(value).to_pydatetime()
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=ET)
        else:
            stamp = stamp.astimezone(ET)
    return stamp.isoformat(), stamp.strftime("%b %d, %Y %I:%M:%S %p %Z")


def normalize_favorite_picks_ledger(payload) -> dict:
    source = payload if isinstance(payload, dict) else {}
    ledger = empty_favorite_picks_ledger()
    ledger["last_run_at_et"] = str(source.get("last_run_at_et") or "")
    current = source.get("current_picks")
    ledger["current_picks"] = deepcopy(current) if isinstance(current, dict) else {}
    ledger["events"] = [deepcopy(item) for item in source.get("events", []) if isinstance(item, dict)]
    ledger["runs"] = [deepcopy(item) for item in source.get("runs", []) if isinstance(item, dict)]
    return ledger


def _event_id(event: dict) -> str:
    existing = str(event.get("event_id") or "").strip()
    if existing:
        return existing
    identity = "|".join(
        str(event.get(key) or "")
        for key in (
            "first_detected_at_et",
            "event_type",
            "sector",
            "dropped_symbol",
            "added_symbol",
            "symbol",
            "previous_value",
            "new_value",
        )
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def merge_favorite_picks_ledgers(*payloads) -> dict:
    """Merge local and durable ledgers without changing existing event dates."""

    ledgers = [normalize_favorite_picks_ledger(payload) for payload in payloads]
    output = empty_favorite_picks_ledger()
    event_map: dict[str, dict] = {}
    run_map: dict[str, dict] = {}
    for ledger in ledgers:
        for event in ledger["events"]:
            event = deepcopy(event)
            event["event_id"] = _event_id(event)
            existing = event_map.get(event["event_id"])
            event_date = str(event.get("first_detected_at_et") or "9999")
            existing_date = str((existing or {}).get("first_detected_at_et") or "9999")
            if existing is None or event_date < existing_date:
                event_map[event["event_id"]] = event
        for run in ledger["runs"]:
            run_id = str(run.get("run_id") or "").strip()
            if run_id:
                run_map.setdefault(run_id, deepcopy(run))
    output["events"] = sorted(event_map.values(), key=lambda item: str(item.get("first_detected_at_et") or ""))
    output["runs"] = sorted(run_map.values(), key=lambda item: str(item.get("run_at_et") or ""))
    latest = max(ledgers, key=lambda item: str(item.get("last_run_at_et") or ""), default=output)
    output["last_run_at_et"] = str(latest.get("last_run_at_et") or "")
    output["current_picks"] = deepcopy(latest.get("current_picks") or {})
    return output


def _pick_records(table: pd.DataFrame) -> dict[str, list[dict]]:
    required = {"Sector", "Sector Rank", "Symbol"}
    if table is None or table.empty or not required.issubset(table.columns):
        raise ValueError("Favorite Picks results do not contain the required sector, rank, and symbol fields.")
    output: dict[str, list[dict]] = {}
    for row in table.to_dict(orient="records"):
        sector = str(row.get("Sector") or "Unknown").strip()
        symbol = str(row.get("Symbol") or "").strip().upper()
        if not symbol:
            continue
        output.setdefault(sector, []).append({
            "sector": sector,
            "rank": int(row.get("Sector Rank") or 0),
            "symbol": symbol,
            "name": str(row.get("Name") or symbol),
            "risk_rating": str(row.get("Risk Rating") or "Unknown"),
            "risk_score": round(float(row.get("Risk Score") or 0.0), 4),
            "favorite_score": round(float(row.get("Favorite Score") or 0.0), 4),
            "model_confidence": str(row.get("Model Confidence") or "Unknown"),
        })
    for sector in output:
        output[sector].sort(key=lambda item: (item["rank"], item["symbol"]))
    return output


def _make_event(stamp: str, display: str, event_type: str, sector: str, **values) -> dict:
    event = {
        "first_detected_at_et": stamp,
        "first_detected_display_et": display,
        "event_type": event_type,
        "sector": sector,
        "source": "MarketScope Favorite Picks",
        **values,
    }
    event["event_id"] = _event_id(event)
    return event


def record_favorite_picks_run(
    ledger: dict | None,
    table: pd.DataFrame,
    observed_at=None,
    data_as_of: str = "",
    random_seed: int | None = None,
) -> tuple[dict, list[dict]]:
    """Append one run and immutable events comparing it with prior saved picks."""

    output = normalize_favorite_picks_ledger(ledger)
    stamp, display = _timestamp(observed_at)
    prior = output.get("current_picks") or {}
    current = _pick_records(table)
    new_events: list[dict] = []

    for sector in sorted(set(prior) | set(current)):
        old_rows = [dict(item) for item in prior.get(sector, []) if isinstance(item, dict)]
        new_rows = [dict(item) for item in current.get(sector, []) if isinstance(item, dict)]
        old_by_symbol = {str(item.get("symbol") or "").upper(): item for item in old_rows}
        new_by_symbol = {str(item.get("symbol") or "").upper(): item for item in new_rows}
        removed = [item for symbol, item in old_by_symbol.items() if symbol not in new_by_symbol]
        added = [item for symbol, item in new_by_symbol.items() if symbol not in old_by_symbol]
        removed.sort(key=lambda item: (int(item.get("rank") or 99), str(item.get("symbol") or "")))
        added.sort(key=lambda item: (int(item.get("rank") or 99), str(item.get("symbol") or "")))

        while removed and added:
            incoming = added.pop(0)
            same_rank_index = next(
                (index for index, item in enumerate(removed) if item.get("rank") == incoming.get("rank")),
                0,
            )
            outgoing = removed.pop(same_rank_index)
            new_events.append(_make_event(
                stamp,
                display,
                "Favorite Pick Replaced",
                sector,
                dropped_symbol=str(outgoing.get("symbol") or ""),
                dropped_name=str(outgoing.get("name") or outgoing.get("symbol") or ""),
                added_symbol=str(incoming.get("symbol") or ""),
                added_name=str(incoming.get("name") or incoming.get("symbol") or ""),
                previous_value=f"{outgoing.get('symbol')} (Rank {outgoing.get('rank')})",
                new_value=f"{incoming.get('symbol')} (Rank {incoming.get('rank')})",
                reason="Sector Top 2 membership changed after a new Favorite Picks calculation.",
            ))
        for outgoing in removed:
            new_events.append(_make_event(
                stamp,
                display,
                "Favorite Pick Removed",
                sector,
                dropped_symbol=str(outgoing.get("symbol") or ""),
                dropped_name=str(outgoing.get("name") or outgoing.get("symbol") or ""),
                previous_value=f"{outgoing.get('symbol')} (Rank {outgoing.get('rank')})",
                new_value="No replacement in eligible Top 2",
                reason="The stock is no longer in the eligible sector Top 2.",
            ))
        for incoming in added:
            new_events.append(_make_event(
                stamp,
                display,
                "Favorite Pick Added" if old_rows else "Initial Favorite Pick",
                sector,
                added_symbol=str(incoming.get("symbol") or ""),
                added_name=str(incoming.get("name") or incoming.get("symbol") or ""),
                previous_value="Not previously selected",
                new_value=f"{incoming.get('symbol')} (Rank {incoming.get('rank')})",
                reason="The stock entered the eligible sector Top 2.",
            ))

        for symbol in sorted(set(old_by_symbol) & set(new_by_symbol)):
            old = old_by_symbol[symbol]
            new = new_by_symbol[symbol]
            old_risk = str(old.get("risk_rating") or "Unknown")
            new_risk = str(new.get("risk_rating") or "Unknown")
            if old_risk != new_risk:
                new_events.append(_make_event(
                    stamp,
                    display,
                    "Favorite Risk Rating Changed",
                    sector,
                    symbol=symbol,
                    name=str(new.get("name") or symbol),
                    previous_value=old_risk,
                    new_value=new_risk,
                    reason="Modeled downside, volatility, or data-quality evidence changed the Favorite risk rating.",
                ))

        for item in new_rows:
            old = old_by_symbol.get(str(item.get("symbol") or "").upper())
            item["first_selected_at_et"] = str((old or {}).get("first_selected_at_et") or stamp)
            item["first_selected_display_et"] = str((old or {}).get("first_selected_display_et") or display)
            if old and str(old.get("risk_rating") or "Unknown") == str(item.get("risk_rating") or "Unknown"):
                item["risk_rating_first_detected_at_et"] = str(old.get("risk_rating_first_detected_at_et") or stamp)
                item["risk_rating_first_detected_display_et"] = str(old.get("risk_rating_first_detected_display_et") or display)
            else:
                item["risk_rating_first_detected_at_et"] = stamp
                item["risk_rating_first_detected_display_et"] = display
        current[sector] = new_rows

    snapshot_text = json.dumps(current, sort_keys=True, separators=(",", ":"))
    run_id = hashlib.sha256(f"{stamp}|{snapshot_text}".encode("utf-8")).hexdigest()[:24]
    output["runs"].append({
        "run_id": run_id,
        "run_at_et": stamp,
        "run_display_et": display,
        "data_as_of": str(data_as_of or "Latest available"),
        "random_seed": int(random_seed) if random_seed is not None else None,
        "sector_count": len(current),
        "pick_count": sum(len(rows) for rows in current.values()),
        "picks": deepcopy(current),
    })
    output["events"].extend(new_events)
    output["events"] = sorted(output["events"], key=lambda item: str(item.get("first_detected_at_et") or ""))
    output["current_picks"] = current
    output["last_run_at_et"] = stamp
    return output, new_events


def favorite_change_history_frame(ledger: dict | None) -> pd.DataFrame:
    columns = [
        "First Detected (ET)", "Sector", "Change Type", "Dropped Pick", "Dropped Company", "New Pick", "New Company",
        "Symbol", "Previous Risk", "New Risk", "Reason", "Source",
    ]
    rows = []
    for event in normalize_favorite_picks_ledger(ledger)["events"]:
        event_type = str(event.get("event_type") or "Change")
        symbol = str(event.get("symbol") or "")
        previous_risk = str(event.get("previous_value") or "") if "Risk Rating" in event_type else ""
        new_risk = str(event.get("new_value") or "") if "Risk Rating" in event_type else ""
        rows.append({
            "_sort": str(event.get("first_detected_at_et") or ""),
            "First Detected (ET)": str(event.get("first_detected_display_et") or event.get("first_detected_at_et") or "Unknown"),
            "Sector": str(event.get("sector") or "Unknown"),
            "Change Type": event_type,
            "Dropped Pick": str(event.get("dropped_symbol") or ""),
            "Dropped Company": str(event.get("dropped_name") or ""),
            "New Pick": str(event.get("added_symbol") or ""),
            "New Company": str(event.get("added_name") or ""),
            "Symbol": symbol,
            "Previous Risk": previous_risk,
            "New Risk": new_risk,
            "Reason": str(event.get("reason") or ""),
            "Source": str(event.get("source") or "MarketScope Favorite Picks"),
        })
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows).sort_values("_sort", ascending=False).drop(columns="_sort")[columns].reset_index(drop=True)


def favorite_run_history_frame(ledger: dict | None) -> pd.DataFrame:
    columns = ["Run Date / Time (ET)", "Data As Of", "Sectors", "Picks", "Random Seed"]
    rows = [
        {
            "_sort": str(run.get("run_at_et") or ""),
            "Run Date / Time (ET)": str(run.get("run_display_et") or run.get("run_at_et") or "Unknown"),
            "Data As Of": str(run.get("data_as_of") or "Latest available"),
            "Sectors": int(run.get("sector_count") or 0),
            "Picks": int(run.get("pick_count") or 0),
            "Random Seed": run.get("random_seed"),
        }
        for run in normalize_favorite_picks_ledger(ledger)["runs"]
    ]
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows).sort_values("_sort", ascending=False).drop(columns="_sort")[columns].reset_index(drop=True)
