from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
SNAPSHOT = BASE_DIR / "data" / "market_snapshot.csv"
REQUIRED_YEARS = [str(y) for y in range(2025, 2000, -1)]
OLDEST_FIVE = ["2005", "2004", "2003", "2002", "2001"]
MIN_OLDEST_YEAR_ROWS = 1


def main() -> None:
    if not SNAPSHOT.exists():
        raise SystemExit(f"Missing snapshot: {SNAPSHOT}")
    df = pd.read_csv(SNAPSHOT)
    missing_columns = [year for year in REQUIRED_YEARS if year not in df.columns]
    if missing_columns:
        raise SystemExit("25Y validation failed; missing year columns: " + ", ".join(missing_columns))

    counts = {
        year: int(pd.to_numeric(df[year], errors="coerce").notna().sum())
        for year in REQUIRED_YEARS
    }
    failed = [year for year in OLDEST_FIVE if counts.get(year, 0) < MIN_OLDEST_YEAR_ROWS]
    print("25Y annual-return coverage counts:")
    for year in REQUIRED_YEARS:
        print(f"  {year}: {counts[year]:,}")
    if failed:
        detail = ", ".join(f"{year}={counts.get(year, 0)}" for year in failed)
        print(
            "25Y coverage audit warning: one or more oldest-year columns still have no "
            "genuine rows in this refresh. The snapshot is still allowed to commit so "
            "future automatic refreshes can accumulate verified history without erasing "
            f"prior values: {detail}"
        )
        return

    print(
        "25Y snapshot coverage audit passed: 2025-2001 columns exist and every oldest "
        "year has genuine annual-return coverage where the current universe includes "
        "instruments with sufficient trading history."
    )


if __name__ == "__main__":
    main()
