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
BOOTSTRAP_UNIVERSE_FILE = BASE_DIR / "data" / "default_universe.bootstrap.csv"
ALL_UNIVERSE_SENTINEL = "__ALL_UNIVERSE__"

MIN_STOCK_MARKET_CAP = 100_000_000_000.0


def _enforce_100b_universe(df: pd.DataFrame) -> pd.DataFrame:
    """Keep Nasdaq-screened stocks strictly above $100B plus ETFs/manual additions.

    The generated daily universe is already filtered at the source-refresh step.
    This defensive filter also prevents an older v5.2 >$100M generated file from
    leaking smaller stocks into the UI immediately after a code-only upgrade.
    """
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if "Type" not in out.columns:
        return out
    types = out["Type"].astype(str).str.upper().str.strip()
    caps = pd.to_numeric(out["MarketCap"], errors="coerce") if "MarketCap" in out.columns else pd.Series(float("nan"), index=out.index)
    source = out.get("Source", pd.Series("", index=out.index)).astype(str).str.lower()
    manual = source.str.contains("manual", regex=False, na=False)
    keep = types.ne("STOCK") | (caps > MIN_STOCK_MARKET_CAP) | manual
    return out.loc[keep].copy()


def is_render_runtime() -> bool:
    """Render exposes RENDER_EXTERNAL_HOSTNAME to running web services."""
    return bool(os.getenv("RENDER_EXTERNAL_HOSTNAME")) or os.getenv("RENDER", "").strip().lower() == "true"


def _normalize_symbols(values) -> List[str]:
    return list(dict.fromkeys(str(x).strip().upper() for x in values if str(x).strip()))


def _read_universe_file(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
    except Exception:
        return pd.DataFrame()
    if df.empty or "Symbol" not in df.columns:
        return pd.DataFrame()
    df["Symbol"] = df["Symbol"].astype(str).str.strip().str.upper()
    return df.drop_duplicates("Symbol", keep="first")


def load_default_universe() -> pd.DataFrame:
    """Load durable generated universe, falling back to upgrade-safe bootstrap.

    v5.3 intentionally does not ship a generated default_universe.csv. That file
    is owned by the daily GitHub Action and must survive application upgrades.
    A fresh repository can still start from default_universe.bootstrap.csv until
    the first action creates the generated file.
    """
    generated = _read_universe_file(UNIVERSE_FILE)
    if not generated.empty:
        filtered = _enforce_100b_universe(generated)
        if not filtered.empty:
            return filtered
    bootstrap = _read_universe_file(BOOTSTRAP_UNIVERSE_FILE)
    if not bootstrap.empty:
        filtered = _enforce_100b_universe(bootstrap)
        if not filtered.empty:
            return filtered
    raise FileNotFoundError(
        "No market universe is available. Run the GitHub Action or restore "
        "data/default_universe.bootstrap.csv."
    )


def _expand_all(values: List[str]) -> List[str]:
    if ALL_UNIVERSE_SENTINEL in values:
        return load_default_universe()["Symbol"].tolist()
    return values


def load_watchlist() -> List[str]:
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
        return
    LOCAL_WATCHLIST_FILE.write_text(json.dumps(symbols, indent=2), encoding="utf-8")
