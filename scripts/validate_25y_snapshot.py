from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from history_config import (
    ANNUAL_HISTORY_FIRST_YEAR,
    annual_history_year_count,
    annual_history_year_labels,
    latest_completed_year,
)

SNAPSHOT = BASE_DIR / "data" / "market_snapshot.csv"
REQUIRED_YEARS = annual_history_year_labels()
OLDEST_FIVE = REQUIRED_YEARS[-5:] if len(REQUIRED_YEARS) >= 5 else list(REQUIRED_YEARS)
MIN_OLDEST_YEAR_ROWS = 1


def main() -> None:
    if not SNAPSHOT.exists():
        raise SystemExit(f"Missing MarketScope snapshot: {SNAPSHOT}")

    df = pd.read_csv(SNAPSHOT)
    missing_columns = [year for year in REQUIRED_YEARS if year not in df.columns]
    if missing_columns:
        raise SystemExit(
            "Dynamic annual-history schema is incomplete. Missing columns: "
            + ", ".join(missing_columns)
        )

    coverage = {
        year: int(pd.to_numeric(df[year], errors="coerce").notna().sum())
        for year in REQUIRED_YEARS
    }
    oldest_coverage = coverage.get(str(ANNUAL_HISTORY_FIRST_YEAR), 0)

    print(
        f"Dynamic annual-history audit: {annual_history_year_count()} completed years, "
        f"{ANNUAL_HISTORY_FIRST_YEAR}-{latest_completed_year()}."
    )
    for year in REQUIRED_YEARS:
        print(f"  {year}: {coverage[year]:,} instrument(s)")

    if oldest_coverage < MIN_OLDEST_YEAR_ROWS:
        print(
            f"WARNING: the baseline year {ANNUAL_HISTORY_FIRST_YEAR} currently has "
            f"{oldest_coverage} populated row(s). The schema remains valid, but the "
            "provider may not have completed the oldest-year backfill yet."
        )

    oldest_five_cells = sum(coverage.get(year, 0) for year in OLDEST_FIVE)
    if oldest_five_cells <= 0:
        raise SystemExit(
            "Dynamic annual-history audit failed: none of the oldest tracked years "
            "contains a genuine saved annual return."
        )

    print(
        f"Dynamic annual-history coverage audit passed through {latest_completed_year()}. "
        "The next completed calendar year will be added automatically without code changes."
    )


if __name__ == "__main__":
    main()
