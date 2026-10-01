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
# Extra fallback locations protect against GitHub web uploads that accidentally
# place the CSVs at the repository root instead of inside data/.
ROOT_UNIVERSE_FILE = BASE_DIR / "default_universe.csv"
ROOT_BOOTSTRAP_UNIVERSE_FILE = BASE_DIR / "default_universe.bootstrap.csv"
ALL_UNIVERSE_SENTINEL = "__ALL_UNIVERSE__"

MIN_STOCK_MARKET_CAP = 100_000_000_000.0


def _enforce_100b_universe(df: pd.DataFrame, *, allow_bootstrap_unknown_caps: bool = False) -> pd.DataFrame:
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
    bootstrap = source.str.contains("bootstrap", regex=False, na=False)
    emergency_bootstrap_stock = allow_bootstrap_unknown_caps & bootstrap & caps.isna()
    keep = types.ne("STOCK") | (caps > MIN_STOCK_MARKET_CAP) | manual | emergency_bootstrap_stock
    return out.loc[keep].copy()


def is_render_runtime() -> bool:
    """Render exposes RENDER_EXTERNAL_HOSTNAME to running web services."""
    return bool(os.getenv("RENDER_EXTERNAL_HOSTNAME")) or os.getenv("RENDER", "").strip().lower() == "true"


def _normalize_symbols(values) -> List[str]:
    return list(dict.fromkeys(str(x).strip().upper() for x in values if str(x).strip()))


def _read_universe_file(path: Path) -> pd.DataFrame:
    """Read a universe CSV defensively.

    GitHub/Excel exports can arrive as UTF-8, UTF-8 with BOM, or Windows-1252.
    v5.4 previously treated any decoding error as an empty file, which could
    incorrectly raise FileNotFoundError even when the CSV existed.
    """
    if not path.exists():
        return pd.DataFrame()

    df = pd.DataFrame()
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
        try:
            df = pd.read_csv(path, encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
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
    # Prefer the generated server-side universe. Then try the bootstrap. Root
    # locations are accepted as a recovery path for accidental GitHub uploads.
    for path in (UNIVERSE_FILE, ROOT_UNIVERSE_FILE):
        generated = _read_universe_file(path)
        if not generated.empty:
            filtered = _enforce_100b_universe(generated)
            if not filtered.empty:
                return filtered

    for path in (BOOTSTRAP_UNIVERSE_FILE, ROOT_BOOTSTRAP_UNIVERSE_FILE):
        bootstrap = _read_universe_file(path)
        if not bootstrap.empty:
            filtered = _enforce_100b_universe(bootstrap, allow_bootstrap_unknown_caps=True)
            if not filtered.empty:
                return filtered

    raise FileNotFoundError(
        "No market universe is available. Expected data/default_universe.csv or "
        "data/default_universe.bootstrap.csv (root-level copies are also accepted). "
        "Run the GitHub Action or restore one of those files."
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
