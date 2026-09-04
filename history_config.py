from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# MarketScope's durable annual-history baseline. This does not cap the ending
# year; it only defines the oldest completed calendar year MarketScope tracks.
ANNUAL_HISTORY_FIRST_YEAR = int(os.getenv("MARKETSCOPE_ANNUAL_HISTORY_FIRST_YEAR", "2001"))
ANNUAL_HISTORY_ANCHOR_YEAR = ANNUAL_HISTORY_FIRST_YEAR - 1
ANNUAL_HISTORY_START = os.getenv(
    "MARKETSCOPE_ANNUAL_HISTORY_START",
    f"{ANNUAL_HISTORY_ANCHOR_YEAR}-01-01",
)


def current_et() -> datetime:
    return datetime.now(ET)


def latest_completed_year(as_of: datetime | None = None) -> int:
    stamp = as_of or current_et()
    return int(stamp.year) - 1


def annual_history_year_count(as_of: datetime | None = None) -> int:
    """Return the lifetime completed-year count from the fixed 2001 baseline.

    Examples:
    - during 2026 -> 25 years (2001-2025)
    - during 2027 -> 26 years (2001-2026)
    - during 2028 -> 27 years (2001-2027)
    """
    last = latest_completed_year(as_of)
    return max(0, last - ANNUAL_HISTORY_FIRST_YEAR + 1)


def annual_history_year_labels(as_of: datetime | None = None) -> list[str]:
    """Newest-to-oldest completed calendar-year labels, growing automatically."""
    last = latest_completed_year(as_of)
    if last < ANNUAL_HISTORY_FIRST_YEAR:
        return []
    return [str(year) for year in range(last, ANNUAL_HISTORY_FIRST_YEAR - 1, -1)]


def annual_horizon_options(as_of: datetime | None = None) -> list[str]:
    return [f"{years}Y" for years in range(1, annual_history_year_count(as_of) + 1)]


def chart_year_labels(as_of: datetime | None = None, include_current: bool = True) -> list[str]:
    """Current year plus every tracked historical calendar year."""
    stamp = as_of or current_et()
    start = int(stamp.year) if include_current else latest_completed_year(stamp)
    if start < ANNUAL_HISTORY_FIRST_YEAR:
        return [str(start)]
    return [str(year) for year in range(start, ANNUAL_HISTORY_FIRST_YEAR - 1, -1)]


def rolling_completed_year_labels(years: int, as_of: datetime | None = None) -> list[str]:
    """Newest-to-oldest rolling completed-year labels for fixed-horizon products."""
    count = max(1, int(years))
    last = latest_completed_year(as_of)
    return [str(year) for year in range(last, last - count, -1)]
