from __future__ import annotations

import io
import os
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parents[1]
import sys
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from history_config import annual_history_year_labels
SNAPSHOT_FILE = BASE_DIR / "data" / "market_snapshot.csv"

YEAR_COLS = annual_history_year_labels()
DEFAULT_TOLERANCE_PP = 0.25
DEFAULT_STOOQ_BULK_URL = "https://static.stooq.com/db/h/d_us_txt.zip"
DEFAULT_ARCHIVE_PATH = BASE_DIR / ".cache" / "stooq" / "d_us_txt.zip"

VERIFICATION_STRING_COLS = [
    "History Verification",
    "Verification Coverage",
    "Verification Exceptions",
    "Verification Source",
    "Verification Updated ET",
]
VERIFICATION_NUMERIC_COLS = [
    "Verified Years",
    "Verification Available Years",
    "Verification Compared Years",
    "Verification Discrepancies",
    "Max Verification Diff (pp)",
    "Verification Tolerance (pp)",
]


def _stamp() -> str:
    return datetime.now(ZoneInfo("America/New_York")).strftime("%b %d, %Y %I:%M:%S %p %Z")


def _safe_float(value):
    try:
        value = float(value)
    except Exception:
        return None
    return value if np.isfinite(value) else None


def _download_archive(path: Path, url: str) -> Path:
    if path.exists() and path.stat().st_size > 1_000_000:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".part")
    if temp.exists():
        temp.unlink()
    print(f"Downloading independent Stooq U.S. bulk history: {url}")
    with requests.get(
        url,
        stream=True,
        timeout=(15, 180),
        headers={"User-Agent": "MarketScope/5.9.61 historical-verification"},
    ) as response:
        response.raise_for_status()
        with temp.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    fh.write(chunk)
    if temp.stat().st_size <= 1_000_000:
        raise RuntimeError(f"Stooq archive response is unexpectedly small ({temp.stat().st_size} bytes).")
    if not zipfile.is_zipfile(temp):
        raise RuntimeError("Stooq bulk response is not a valid ZIP archive.")
    temp.replace(path)
    return path


def _member_index(zf: zipfile.ZipFile) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in zf.namelist():
        if not name.lower().endswith(".txt"):
            continue
        base = Path(name).name.lower()
        result.setdefault(base, name)
    return result


def _stooq_member_candidates(symbol: str) -> list[str]:
    sym = str(symbol or "").strip().lower()
    if not sym:
        return []
    forms = [
        sym,
        sym.replace(".", "-"),
        sym.replace("/", "-"),
    ]
    out = []
    for form in forms:
        candidate = f"{form}.us.txt"
        if candidate not in out:
            out.append(candidate)
    return out


def _parse_stooq_year_end_closes(raw: bytes) -> dict[int, float]:
    frame = pd.read_csv(io.BytesIO(raw))
    if frame.empty:
        return {}
    frame.columns = [str(c).strip().strip("<>").upper() for c in frame.columns]
    if "DATE" not in frame.columns or "CLOSE" not in frame.columns:
        return {}
    dates = pd.to_datetime(
        frame["DATE"].astype(str).str.replace(r"\.0$", "", regex=True),
        format="%Y%m%d",
        errors="coerce",
    )
    close = pd.to_numeric(frame["CLOSE"], errors="coerce")
    clean = pd.DataFrame({"date": dates, "close": close}).dropna()
    clean = clean.loc[(clean["close"] > 0)].sort_values("date")
    if clean.empty:
        return {}
    clean["year"] = clean["date"].dt.year
    return {
        int(year): float(group.iloc[-1]["close"])
        for year, group in clean.groupby("year", sort=True)
        if not group.empty
    }


def _annual_returns_from_year_ends(year_ends: dict[int, float]) -> dict[str, float]:
    result: dict[str, float] = {}
    for year_text in YEAR_COLS:
        year = int(year_text)
        start = year_ends.get(year - 1)
        finish = year_ends.get(year)
        if start is None or finish is None or start <= 0 or finish <= 0:
            continue
        result[year_text] = (finish / start - 1.0) * 100.0
    return result


def _verification_for_row(
    row: pd.Series,
    secondary_returns: dict[str, float],
    tolerance_pp: float,
) -> dict:
    yahoo: dict[str, float] = {}
    for year in YEAR_COLS:
        value = _safe_float(row.get(year))
        if value is not None:
            yahoo[year] = value

    available = len(yahoo)
    compared = 0
    verified = 0
    exceptions = []
    max_diff = None

    for year, primary in yahoo.items():
        secondary = _safe_float(secondary_returns.get(year))
        if secondary is None:
            continue
        compared += 1
        diff = abs(primary - secondary)
        max_diff = diff if max_diff is None else max(max_diff, diff)
        if diff <= tolerance_pp:
            verified += 1
        else:
            exceptions.append(
                f"{year}: Yahoo {primary:+.2f}% vs Stooq {secondary:+.2f}% (Δ {diff:.2f}pp)"
            )

    discrepancies = len(exceptions)
    if compared == 0:
        status = "Unavailable"
    elif discrepancies:
        status = "Review"
    elif compared == available:
        status = "Verified"
    else:
        status = "Partial"

    return {
        "History Verification": status,
        "Verification Coverage": f"{compared}/{available}" if available else "0/0",
        "Verified Years": int(verified),
        "Verification Available Years": int(available),
        "Verification Compared Years": int(compared),
        "Verification Discrepancies": int(discrepancies),
        "Max Verification Diff (pp)": round(float(max_diff), 4) if max_diff is not None else np.nan,
        "Verification Tolerance (pp)": float(tolerance_pp),
        "Verification Exceptions": " | ".join(exceptions),
        "Verification Source": "Stooq U.S. bulk historical Close cross-check",
        "Verification Updated ET": _stamp(),
    }


def _ensure_verification_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for col in VERIFICATION_STRING_COLS:
        if col not in out.columns:
            out[col] = ""
    for col in VERIFICATION_NUMERIC_COLS:
        if col not in out.columns:
            out[col] = np.nan
    return out


def verify_snapshot(
    snapshot: pd.DataFrame,
    archive_path: Path,
    tolerance_pp: float = DEFAULT_TOLERANCE_PP,
) -> pd.DataFrame:
    snapshot = _ensure_verification_columns(snapshot)
    if snapshot.empty or "Symbol" not in snapshot.columns:
        return snapshot

    with zipfile.ZipFile(archive_path, "r") as zf:
        members = _member_index(zf)
        for idx, row in snapshot.iterrows():
            symbol = str(row.get("Symbol") or "").strip().upper()
            if not symbol:
                continue
            member = None
            for candidate in _stooq_member_candidates(symbol):
                if candidate in members:
                    member = members[candidate]
                    break

            if member is None:
                result = _verification_for_row(row, {}, tolerance_pp)
                result["Verification Source"] = "Stooq U.S. bulk history — symbol unavailable"
            else:
                try:
                    year_ends = _parse_stooq_year_end_closes(zf.read(member))
                    secondary = _annual_returns_from_year_ends(year_ends)
                    result = _verification_for_row(row, secondary, tolerance_pp)
                except Exception as exc:
                    result = _verification_for_row(row, {}, tolerance_pp)
                    result["Verification Source"] = f"Stooq cross-check unavailable: {type(exc).__name__}"

            for col, value in result.items():
                snapshot.at[idx, col] = value

    return snapshot


def main() -> int:
    if not SNAPSHOT_FILE.exists():
        print("market_snapshot.csv is unavailable; verification skipped.")
        return 0

    tolerance = float(os.getenv("MARKETSCOPE_VERIFICATION_TOLERANCE_PP", str(DEFAULT_TOLERANCE_PP)))
    archive_path = Path(os.getenv("MARKETSCOPE_STOOQ_ARCHIVE_PATH", str(DEFAULT_ARCHIVE_PATH)))
    archive_url = os.getenv("MARKETSCOPE_STOOQ_BULK_URL", DEFAULT_STOOQ_BULK_URL)

    original = pd.read_csv(SNAPSHOT_FILE)
    try:
        archive = _download_archive(archive_path, archive_url)
        verified = verify_snapshot(original, archive, tolerance)
    except Exception as exc:
        # Verification is quality metadata, not the primary market-price source.
        # Never block or erase an otherwise valid Yahoo snapshot because the
        # independent provider is temporarily unavailable.
        print(f"WARNING: independent annual-return verification skipped: {exc}")
        preserved = _ensure_verification_columns(original)
        preserved.to_csv(SNAPSHOT_FILE, index=False)
        return 0

    temp = SNAPSHOT_FILE.with_suffix(".verification.tmp")
    verified.to_csv(temp, index=False)
    temp.replace(SNAPSHOT_FILE)

    status_counts = verified["History Verification"].fillna("").value_counts().to_dict()
    print(f"Historical verification complete with tolerance {tolerance:.2f} percentage points.")
    print(f"Status counts: {status_counts}")
    review = int((verified["History Verification"] == "Review").sum())
    compared = int(pd.to_numeric(verified["Verification Compared Years"], errors="coerce").fillna(0).sum())
    print(f"Compared {compared:,} annual-return cells; {review:,} instrument(s) require review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
