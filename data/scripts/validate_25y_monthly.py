from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from history_config import annual_history_year_labels

ANNUAL_FILE = BASE_DIR / "data" / "market_snapshot.csv"
MONTHLY_FILE = BASE_DIR / "data" / "monthly_returns_full_history.csv"
YEARS = annual_history_year_labels()
TOLERANCE_PP = 0.05


def _compound_months(row: pd.Series, year: str) -> float | None:
    factor = 1.0
    for month in range(1, 13):
        value = pd.to_numeric(
            pd.Series([row.get(f"{year}-{month:02d}")]), errors="coerce"
        ).iloc[0]
        if pd.isna(value) or not np.isfinite(value) or float(value) <= -100.0:
            return None
        factor *= 1.0 + float(value) / 100.0
    return (factor - 1.0) * 100.0


def main() -> None:
    if not ANNUAL_FILE.exists():
        raise SystemExit(f"Missing annual snapshot: {ANNUAL_FILE}")
    if not MONTHLY_FILE.exists():
        raise SystemExit(f"Missing dynamic actual-monthly snapshot: {MONTHLY_FILE}")

    annual = pd.read_csv(ANNUAL_FILE)
    monthly = pd.read_csv(MONTHLY_FILE)
    if "Symbol" not in annual.columns or "Symbol" not in monthly.columns:
        raise SystemExit("Annual/monthly files must contain Symbol.")
    if "Monthly Return Method" not in monthly.columns:
        raise SystemExit("Dynamic monthly file is missing Monthly Return Method.")

    methods = monthly["Monthly Return Method"].dropna().astype(str)
    if methods.empty or not methods.str.contains(
        "Actual adjusted month-end return", case=False, regex=False
    ).all():
        raise SystemExit("Dynamic monthly file contains non-actual return methodology.")

    annual["Symbol"] = annual["Symbol"].astype(str).str.upper().str.strip()
    monthly["Symbol"] = monthly["Symbol"].astype(str).str.upper().str.strip()
    annual = annual.drop_duplicates("Symbol", keep="last").set_index("Symbol", drop=False)
    monthly = monthly.drop_duplicates("Symbol", keep="last").set_index("Symbol", drop=False)

    compared = 0
    mismatches: list[str] = []
    coverage_by_year = {year: 0 for year in YEARS}

    for symbol in sorted(annual.index):
        arow = annual.loc[symbol]
        if isinstance(arow, pd.DataFrame):
            arow = arow.iloc[-1]
        has_annual = any(
            pd.notna(
                pd.to_numeric(pd.Series([arow.get(year)]), errors="coerce").iloc[0]
            )
            for year in YEARS
        )
        if has_annual and symbol not in monthly.index:
            mismatches.append(
                f"{symbol}: annual Market Table history exists but the dynamic monthly row is missing"
            )

    for symbol in sorted(set(annual.index).intersection(monthly.index)):
        arow = annual.loc[symbol]
        mrow = monthly.loc[symbol]
        if isinstance(arow, pd.DataFrame):
            arow = arow.iloc[-1]
        if isinstance(mrow, pd.DataFrame):
            mrow = mrow.iloc[-1]

        for year in YEARS:
            aval = pd.to_numeric(pd.Series([arow.get(year)]), errors="coerce").iloc[0]
            if pd.isna(aval) or not np.isfinite(aval):
                continue

            compounded = _compound_months(mrow, year)
            if compounded is None:
                # An annual return needs prior-year-end and year-end anchors, but a
                # full 12-month monthly sequence also needs every month. Do not
                # fabricate missing monthly observations.
                mismatches.append(
                    f"{symbol} {year}: annual return exists but 12 actual monthly returns are incomplete"
                )
                continue

            coverage_by_year[year] += 1
            compared += 1
            diff = abs(float(aval) - float(compounded))
            if diff > TOLERANCE_PP:
                mismatches.append(
                    f"{symbol} {year}: annual {float(aval):+.4f}% vs monthly compound "
                    f"{float(compounded):+.4f}% (delta {diff:.4f}pp)"
                )

    print(f"Dynamic monthly/annual reconciliation cells compared: {compared:,}")
    for year in YEARS:
        print(f"  {year}: {coverage_by_year[year]:,}")

    if compared == 0:
        raise SystemExit("No annual/monthly cells could be reconciled.")

    if mismatches:
        preview = "\n".join(mismatches[:25])
        raise SystemExit(
            f"Dynamic monthly reconciliation failed with {len(mismatches):,} issue(s) "
            f"above {TOLERANCE_PP:.2f}pp or with missing monthly anchors:\n{preview}"
        )

    print(
        f"Dynamic monthly reconciliation passed across {len(YEARS)} completed years. "
        "A newly completed year will be included automatically on the next annual refresh."
    )


if __name__ == "__main__":
    main()
