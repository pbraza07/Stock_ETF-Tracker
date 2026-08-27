from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_WATCHLIST_FILE = BASE_DIR / "data" / "watchlist.json"
LOCAL_WATCHLIST_FILE = BASE_DIR / "data" / "watchlist.local.json"
UNIVERSE_FILE = BASE_DIR / "data" / "default_universe.csv"


def is_render_runtime() -> bool:
    """Render exposes RENDER_EXTERNAL_HOSTNAME to running web services."""
    return bool(os.getenv("RENDER_EXTERNAL_HOSTNAME"))


def _normalize_symbols(values) -> List[str]:
    return list(dict.fromkeys(str(x).strip().upper() for x in values if str(x).strip()))


def load_default_universe() -> pd.DataFrame:
    return pd.read_csv(UNIVERSE_FILE)


def load_watchlist() -> List[str]:
    # Local desktop launches get a separate mutable file so Git never sees
    # ordinary watchlist changes. Render Free is ephemeral, so cloud sessions
    # intentionally start from the committed seed and app.py mirrors changes
    # into the URL query string for bookmarkable persistence.
    candidates = [DEFAULT_WATCHLIST_FILE] if is_render_runtime() else [LOCAL_WATCHLIST_FILE, DEFAULT_WATCHLIST_FILE]
    for path in candidates:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                return _normalize_symbols(data)
        except Exception:
            continue
    return load_default_universe()["Symbol"].astype(str).str.upper().tolist()


def save_watchlist(symbols: List[str]) -> None:
    symbols = _normalize_symbols(symbols)
    if is_render_runtime():
        # Free Render instances have an ephemeral filesystem. The Streamlit
        # app keeps cloud state in st.session_state + the URL instead.
        return
    LOCAL_WATCHLIST_FILE.write_text(json.dumps(symbols, indent=2), encoding="utf-8")
