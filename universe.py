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
ALL_UNIVERSE_SENTINEL = "__ALL_UNIVERSE__"


def is_render_runtime() -> bool:
    """Render exposes RENDER_EXTERNAL_HOSTNAME to running web services."""
    return bool(os.getenv("RENDER_EXTERNAL_HOSTNAME")) or os.getenv("RENDER", "").strip().lower() == "true"


def _normalize_symbols(values) -> List[str]:
    return list(dict.fromkeys(str(x).strip().upper() for x in values if str(x).strip()))


def load_default_universe() -> pd.DataFrame:
    df = pd.read_csv(UNIVERSE_FILE)
    df["Symbol"] = df["Symbol"].astype(str).str.strip().str.upper()
    return df.drop_duplicates("Symbol", keep="first")


def _expand_all(values: List[str]) -> List[str]:
    if ALL_UNIVERSE_SENTINEL in values:
        return load_default_universe()["Symbol"].tolist()
    return values


def load_watchlist() -> List[str]:
    # Local desktop launches can use a mutable watchlist.local.json. Render's
    # filesystem is ephemeral, so the committed watchlist defaults to the
    # special ALL_UNIVERSE sentinel and URL parameters can represent subsets.
    candidates = [DEFAULT_WATCHLIST_FILE] if is_render_runtime() else [LOCAL_WATCHLIST_FILE, DEFAULT_WATCHLIST_FILE]
    for path in candidates:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                return _expand_all(_normalize_symbols(data))
        except Exception:
            continue
    return load_default_universe()["Symbol"].tolist()


def save_watchlist(symbols: List[str]) -> None:
    symbols = _normalize_symbols(symbols)
    if is_render_runtime():
        # Render Free storage is ephemeral. Cloud state remains in the session
        # and URL; durable cross-device watchlists need an external persistence
        # layer (not a market-data API).
        return
    LOCAL_WATCHLIST_FILE.write_text(json.dumps(symbols, indent=2), encoding="utf-8")
