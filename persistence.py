from __future__ import annotations

import base64
import json
import os
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

import pandas as pd
import requests

ET = ZoneInfo("America/New_York")
DEFAULT_REPO = os.getenv("MARKETSCOPE_GITHUB_REPO", "pbraza07/Stock_ETF-Tracker")
DEFAULT_BRANCH = os.getenv("MARKETSCOPE_GITHUB_BRANCH", "main")
SNAPSHOT_PATH = "data/market_snapshot.csv"
METADATA_PATH = "data/snapshot_metadata.json"
UNIVERSE_METADATA_PATH = "data/universe_metadata.json"


def now_et() -> datetime:
    return datetime.now(ET)


def format_et(dt: Optional[datetime] = None) -> str:
    dt = dt or now_et()
    return dt.astimezone(ET).strftime("%b %d, %Y %I:%M:%S %p %Z")


def _raw_url(path: str) -> str:
    return f"https://raw.githubusercontent.com/{DEFAULT_REPO}/{DEFAULT_BRANCH}/{path}"


def load_remote_snapshot(timeout: int = 8) -> pd.DataFrame:
    try:
        response = requests.get(_raw_url(SNAPSHOT_PATH), timeout=timeout)
        response.raise_for_status()
        return pd.read_csv(StringIO(response.text))
    except Exception:
        return pd.DataFrame()


def load_remote_metadata(timeout: int = 8) -> dict:
    try:
        response = requests.get(_raw_url(METADATA_PATH), timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def load_remote_universe_metadata(timeout: int = 8) -> dict:
    try:
        response = requests.get(_raw_url(UNIVERSE_METADATA_PATH), timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "MarketScope-Render",
    }


def _put_text_file(path: str, text: str, message: str, token: str) -> Tuple[bool, str]:
    url = f"https://api.github.com/repos/{DEFAULT_REPO}/contents/{path}"
    headers = _headers(token)
    try:
        current = requests.get(url, headers=headers, params={"ref": DEFAULT_BRANCH}, timeout=15)
        sha = (current.json() or {}).get("sha") if current.status_code == 200 else None
        if current.status_code not in (200, 404):
            return False, f"GitHub read failed ({current.status_code})"
        body = {
            "message": message,
            "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
            "branch": DEFAULT_BRANCH,
        }
        if sha:
            body["sha"] = sha
        saved = requests.put(url, headers=headers, json=body, timeout=30)
        if saved.status_code not in (200, 201):
            return False, f"GitHub save failed ({saved.status_code}): {saved.text[:220]}"
        return True, "Saved to GitHub"
    except Exception as exc:
        return False, f"GitHub persistence error: {exc}"


def persist_snapshot(df: pd.DataFrame, local_path: Path, source: str, updated_count: int) -> Tuple[bool, str]:
    """Save immediately on Render and durably in GitHub.

    Render Free storage is ephemeral. GitHub is the durable source of truth,
    while the local copy makes the refreshed data immediately visible to every
    browser hitting the current Render process.
    """
    local_path.parent.mkdir(parents=True, exist_ok=True)
    csv_text = df.to_csv(index=False)
    local_path.write_text(csv_text, encoding="utf-8")

    stamp = now_et()
    metadata = {
        "updated_at_et": stamp.isoformat(),
        "updated_at_display_et": format_et(stamp),
        "timezone": "America/New_York",
        "source": source,
        "updated_instruments": int(updated_count),
        "snapshot_rows": int(len(df)),
    }
    meta_text = json.dumps(metadata, indent=2) + "\n"
    (local_path.parent / "snapshot_metadata.json").write_text(meta_text, encoding="utf-8")

    token = os.getenv("MARKETSCOPE_GITHUB_TOKEN", "").strip()
    if not token:
        return False, (
            "Refresh data was saved on the current Render server and is available immediately. "
            "For permanent cross-restart/cross-device persistence, set MARKETSCOPE_GITHUB_TOKEN in Render; "
            "the scheduled 6:00 PM ET GitHub Action remains durable automatically."
        )

    ok, msg = _put_text_file(SNAPSHOT_PATH, csv_text, f"data: manual MarketScope refresh {format_et(stamp)}", token)
    if not ok:
        return False, msg
    ok, msg = _put_text_file(METADATA_PATH, meta_text, f"data: MarketScope refresh metadata {format_et(stamp)}", token)
    if not ok:
        return False, msg
    return True, "Saved permanently to GitHub and locally on Render; every device will use this refreshed snapshot."
