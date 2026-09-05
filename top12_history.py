"""Separate append-only ledgers, atomic local saves and optimistic GitHub merge."""

import base64
import hashlib
import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import requests
from persistence import DEFAULT_REPO, DEFAULT_BRANCH, _headers

_LOCK = threading.RLock()


def ledger_path(kind):
    return (
        Path(__file__).parent
        / "data"
        / ("top12_" + kind.lower().replace(" ", "_") + "_history.json")
    )


def merge_ledgers(*ledgers):
    result = {"runs": [], "events": []}
    for field in result:
        seen = {}
        for ledger in ledgers:
            for item in (ledger or {}).get(field, []):
                seen.setdefault(item["id"], item)
        result[field] = sorted(seen.values(), key=lambda r: (r["Timestamp"], r["id"]))
    return result


def current_table(ledger):
    runs = (ledger or {}).get("runs") or []
    return pd.DataFrame(runs[-1]["Holdings"]) if runs else pd.DataFrame()


def load_ledger(kind, remote=True):
    path = ledger_path(kind)
    local = json.loads(path.read_text()) if path.exists() else {}
    if remote:
        try:
            r = requests.get(
                f"https://raw.githubusercontent.com/{DEFAULT_REPO}/{DEFAULT_BRANCH}/data/{path.name}",
                timeout=5,
            )
            r.raise_for_status()
            return merge_ledgers(local, r.json())
        except (requests.RequestException, ValueError):
            pass
    return merge_ledgers(local)


def record_run(ledger, kind, table, metadata, timestamp=None):
    stamp = timestamp or datetime.now(timezone.utc).isoformat()
    score = kind + " Score"
    rows = json.loads(
        table[["Rank", "Symbol", "Sector", score]].to_json(orient="records")
    )
    fingerprint = hashlib.sha256(
        json.dumps([kind, rows, metadata], sort_keys=True).encode()
    ).hexdigest()
    if any(r["id"] == fingerprint for r in ledger.get("runs", [])):
        return ledger
    old = current_table(ledger)
    before = {r["Symbol"]: r for r in old.to_dict("records")}
    after = {r["Symbol"]: r for r in rows}
    removed = [r for r in before if r not in after]
    added = [r for r in after if r not in before]
    events = []
    pairs = list(zip(removed, added))
    pairs += [(s, None) for s in removed[len(pairs) :]] + [
        (None, s) for s in added[len(pairs) :]
    ]
    pairs += [
        (s, s)
        for s in sorted(after.keys() & before.keys())
        if after[s]["Rank"] != before[s]["Rank"]
    ]
    for i, (out, incoming) in enumerate(pairs):
        events.append(
            {
                "id": fingerprint + f":{i}",
                "Timestamp": stamp,
                "Ranking Type": kind,
                "Ticker Added": incoming if incoming != out else None,
                "Ticker Removed": out if incoming != out else None,
                "Ticker": incoming or out,
                "New Rank": after.get(incoming, {}).get("Rank"),
                "Previous Rank": before.get(out, {}).get("Rank"),
                "New Score": after.get(incoming, {}).get(score),
                "Previous Score": before.get(out, {}).get(score),
                "Reason for Change": (
                    "Initial baseline"
                    if not before
                    else "Recalculated evidence, eligibility, sector cap and configured stability threshold"
                ),
            }
        )
    return merge_ledgers(
        ledger,
        {
            "runs": [
                {
                    "id": fingerprint,
                    "Timestamp": stamp,
                    "Ranking Type": kind,
                    "Holdings": rows,
                    "Metadata": metadata,
                }
            ],
            "events": events,
        },
    )


def _save_local(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, delete=False, suffix=".tmp"
    ) as f:
        json.dump(payload, f, indent=2, allow_nan=False)
        temporary = Path(f.name)
    temporary.replace(path)


def persist_ledger(kind, ledger):
    path = ledger_path(kind)
    with _LOCK:
        candidate = merge_ledgers(load_ledger(kind, remote=False), ledger)
        _save_local(path, candidate)
        token = os.getenv("MARKETSCOPE_GITHUB_TOKEN", "").strip()
        if not token:
            return (
                False,
                "Saved on this server. Durable cross-restart history requires MARKETSCOPE_GITHUB_TOKEN with Contents read/write access.",
            )
        url = f"https://api.github.com/repos/{DEFAULT_REPO}/contents/data/{path.name}"
        try:
            for _ in range(3):
                r = requests.get(
                    url,
                    headers=_headers(token),
                    params={"ref": DEFAULT_BRANCH},
                    timeout=10,
                )
                if r.status_code not in (200, 404):
                    r.raise_for_status()
                body = r.json() if r.status_code == 200 else {}
                other = (
                    json.loads(base64.b64decode(body["content"]))
                    if body.get("content")
                    else {}
                )
                candidate = merge_ledgers(other, candidate)
                payload = {
                    "message": f"data: append {kind} Top 12 history",
                    "branch": DEFAULT_BRANCH,
                    "content": base64.b64encode(
                        json.dumps(candidate, allow_nan=False).encode()
                    ).decode(),
                }
                if body.get("sha"):
                    payload["sha"] = body["sha"]
                saved = requests.put(
                    url, headers=_headers(token), json=payload, timeout=15
                )
                if saved.status_code in (200, 201):
                    _save_local(path, candidate)
                    return True, "Ranking history saved durably to GitHub."
                if saved.status_code not in (409, 422):
                    saved.raise_for_status()
        except (requests.RequestException, ValueError):
            return (
                False,
                "Local history retained; GitHub persistence is temporarily unavailable.",
            )
        return (
            False,
            "Local history retained; concurrent GitHub changes require a retry.",
        )
