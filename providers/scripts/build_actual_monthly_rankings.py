from __future__ import annotations

import heapq
import itertools
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
MONTHLY_FILE = BASE_DIR / "data" / "monthly_returns_10y.csv"
REBALANCED_OUT = BASE_DIR / "data" / "top100_rebalanced_monthly_withdrawal_10y_no_hwm.csv"
NOT_REBALANCED_OUT = BASE_DIR / "data" / "top100_not_rebalanced_monthly_withdrawal_10y_no_hwm.csv"

STARTING_VALUE = 300_000.0
MONTHLY_WITHDRAWAL = 5_000.0
TOP_N = 100
CHUNK_SIZE = 100_000
METHOD = "Actual adjusted month-end return from Yahoo/yfinance daily history"


def _month_columns(df: pd.DataFrame) -> list[str]:
    cols = []
    for col in df.columns:
        text = str(col)
        if len(text) == 7 and text[4] == "-" and text[:4].isdigit() and text[5:].isdigit():
            month = int(text[5:])
            if 1 <= month <= 12:
                cols.append(text)
    cols = sorted(cols)
    if len(cols) < 120:
        raise RuntimeError(f"Expected at least 120 actual monthly return columns, found {len(cols)}.")
    # Use the latest ten complete calendar years contained in the file.
    by_year: dict[str, list[str]] = {}
    for col in cols:
        by_year.setdefault(col[:4], []).append(col)
    complete_years = sorted([y for y, values in by_year.items() if len(values) == 12])
    if len(complete_years) < 10:
        raise RuntimeError("The actual monthly return file does not contain ten complete calendar years.")
    years = complete_years[-10:]
    return [f"{year}-{month:02d}" for year in years for month in range(1, 13)]


def _cartesian_indices(groups: list[np.ndarray]) -> np.ndarray:
    meshes = np.meshgrid(*groups, indexing="ij")
    return np.stack([m.reshape(-1) for m in meshes], axis=1)


def _local_top(values: np.ndarray, alive: np.ndarray, n: int = TOP_N) -> np.ndarray:
    valid = np.flatnonzero(alive & np.isfinite(values))
    if valid.size <= n:
        return valid
    local = values[valid]
    part = np.argpartition(local, -n)[-n:]
    return valid[part]


def _push_top(heap: list[tuple[float, tuple[int, int, int, int]]], balance: float, combo: np.ndarray) -> None:
    item = (float(balance), tuple(int(x) for x in combo))
    if len(heap) < TOP_N:
        heapq.heappush(heap, item)
    elif item[0] > heap[0][0]:
        heapq.heapreplace(heap, item)


def _evaluate_chunk(combo_idx: np.ndarray, factors: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    n = len(combo_idx)
    rb = np.full(n, STARTING_VALUE, dtype="float64")
    rb_alive = np.ones(n, dtype=bool)

    nr = np.full((n, 4), STARTING_VALUE / 4.0, dtype="float64")
    nr_alive = np.ones(n, dtype=bool)

    for month in range(factors.shape[1]):
        month_factors = factors[combo_idx, month]

        rb_before = rb * month_factors.mean(axis=1)
        rb_can_pay = rb_before >= MONTHLY_WITHDRAWAL
        rb_alive &= rb_can_pay
        rb = np.where(rb_alive, rb_before - MONTHLY_WITHDRAWAL, 0.0)

        nr *= month_factors
        nr_before = nr.sum(axis=1)
        nr_can_pay = nr_before >= MONTHLY_WITHDRAWAL
        nr_alive &= nr_can_pay
        nr_after = np.where(nr_alive, nr_before - MONTHLY_WITHDRAWAL, 0.0)
        scale = np.divide(
            nr_after,
            nr_before,
            out=np.zeros_like(nr_after),
            where=nr_before > 0,
        )
        nr *= scale[:, None]

    return rb, rb_alive, nr.sum(axis=1), nr_alive


def _simulate_one(combo: tuple[int, int, int, int], factors: np.ndarray, months: list[str], rebalance: bool) -> dict:
    year_end: dict[str, float] = {}
    year_return_factor: dict[str, float] = {}
    total_withdrawn = 0.0
    months_funded = 0
    positive_months = 0

    if rebalance:
        balance = STARTING_VALUE
        for month_idx, label in enumerate(months):
            monthly_factor = float(factors[list(combo), month_idx].mean())
            year_return_factor[label[:4]] = year_return_factor.get(label[:4], 1.0) * monthly_factor
            if monthly_factor > 1.0:
                positive_months += 1
            before = balance * monthly_factor
            if before < MONTHLY_WITHDRAWAL:
                balance = max(0.0, before)
                break
            balance = before - MONTHLY_WITHDRAWAL
            total_withdrawn += MONTHLY_WITHDRAWAL
            months_funded += 1
            if label.endswith("-12"):
                year_end[label[:4]] = balance
        remaining = balance
    else:
        holdings = np.full(4, STARTING_VALUE / 4.0, dtype="float64")
        for month_idx, label in enumerate(months):
            starting_balance = float(holdings.sum())
            holdings *= factors[list(combo), month_idx]
            before = float(holdings.sum())
            monthly_factor = (before / starting_balance) if starting_balance > 0 else 1.0
            year_return_factor[label[:4]] = year_return_factor.get(label[:4], 1.0) * monthly_factor
            if starting_balance > 0 and before > starting_balance:
                positive_months += 1
            if before < MONTHLY_WITHDRAWAL:
                remaining = max(0.0, before)
                holdings[:] = 0.0
                break
            remaining = before - MONTHLY_WITHDRAWAL
            scale = remaining / before if before > 0 else 0.0
            holdings *= scale
            total_withdrawn += MONTHLY_WITHDRAWAL
            months_funded += 1
            if label.endswith("-12"):
                year_end[label[:4]] = remaining
        else:
            remaining = float(holdings.sum())

    return {
        "year_end": year_end,
        "remaining": float(remaining),
        "total_withdrawn": float(total_withdrawn),
        "months_funded": int(months_funded),
        "positive_months": int(positive_months),
        "annual_returns": {year: (factor - 1.0) * 100.0 for year, factor in year_return_factor.items()},
    }


def _build_output(
    ranked: list[tuple[float, tuple[int, int, int, int]]],
    frame: pd.DataFrame,
    factors: np.ndarray,
    months: list[str],
    rebalance: bool,
) -> pd.DataFrame:
    rows = []
    strategy = "Rebalanced monthly" if rebalance else "Not rebalanced monthly"
    for rank, (_, combo) in enumerate(sorted(ranked, key=lambda x: x[0], reverse=True), start=1):
        sim = _simulate_one(combo, factors, months, rebalance)
        stocks = [str(frame.iloc[i]["Symbol"]) for i in combo]
        sectors = [str(frame.iloc[i]["Sector"]) for i in combo]
        names = [str(frame.iloc[i].get("Name") or stocks[pos]) for pos, i in enumerate(combo)]
        row = {
            "Rank": rank,
            "Combo": " + ".join(stocks),
            "Strategy": strategy,
        }
        for pos, (stock, sector, name) in enumerate(zip(stocks, sectors, names), start=1):
            row[f"Stock {pos}"] = stock
            row[f"Sector {pos}"] = sector
            row[f"Name {pos}"] = name
        year_list = sorted({m[:4] for m in months})
        for year in reversed(year_list):
            row[year] = sim["annual_returns"].get(year, np.nan)
        annual_values = [(year, sim["annual_returns"].get(year)) for year in year_list]
        annual_values = [(year, value) for year, value in annual_values if value is not None and np.isfinite(value)]
        if annual_values:
            worst_year, worst_value = min(annual_values, key=lambda item: item[1])
            best_year, best_value = max(annual_values, key=lambda item: item[1])
            row["Worst Year"] = worst_year
            row["Worst Year %"] = worst_value
            row["Best Year"] = best_year
            row["Best Year %"] = best_value
        for year in year_list:
            row[f"{year} Ending Balance ($)"] = sim["year_end"].get(year, np.nan)
        row.update({
            "Starting Value ($)": STARTING_VALUE,
            "Monthly Withdrawal ($)": MONTHLY_WITHDRAWAL,
            "Total Withdrawn ($)": sim["total_withdrawn"],
            "Remaining Balance ($)": sim["remaining"],
            "Net Value incl. Withdrawals ($)": sim["remaining"] + sim["total_withdrawn"],
            "Net Profit incl. Withdrawals ($)": sim["remaining"] + sim["total_withdrawn"] - STARTING_VALUE,
            "Positive Months": sim["positive_months"],
            "Months Funded": sim["months_funded"],
            "HWM Excluded": True,
            "Monthly Return Method": METHOD,
            "Monthly Data Start": months[0],
            "Monthly Data End": months[-1],
        })
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    if not MONTHLY_FILE.exists():
        raise SystemExit(f"Missing {MONTHLY_FILE}. Run scripts/update_snapshot.py first.")

    raw = pd.read_csv(MONTHLY_FILE)
    raw["Symbol"] = raw["Symbol"].astype(str).str.upper().str.strip()
    raw["Sector"] = raw["Sector"].fillna("Unknown").astype(str).str.strip()
    raw["Type"] = raw["Type"].fillna("").astype(str).str.upper().str.strip()
    months = _month_columns(raw)

    mask = raw["Type"].eq("STOCK") & raw["Symbol"].ne("HWM")
    mask &= ~raw["Sector"].str.lower().isin({"", "unknown", "nan", "none"})
    numeric = raw[months].apply(pd.to_numeric, errors="coerce")
    mask &= numeric.notna().all(axis=1)
    mask &= np.isfinite(numeric.to_numpy(dtype="float64", na_value=np.nan)).all(axis=1)
    eligible = raw.loc[mask, ["Symbol", "Name", "Sector", *months]].copy().reset_index(drop=True)
    returns = eligible[months].apply(pd.to_numeric, errors="coerce").to_numpy(dtype="float64") / 100.0
    factors = 1.0 + returns
    valid_factor = np.isfinite(factors).all(axis=1) & (factors > 0).all(axis=1)
    eligible = eligible.loc[valid_factor].reset_index(drop=True)
    factors = factors[valid_factor]

    if len(eligible) < 4:
        raise RuntimeError("Fewer than four stocks have complete actual monthly history.")

    sector_groups: dict[str, np.ndarray] = {}
    for sector, group in eligible.groupby("Sector", sort=True):
        sector_groups[str(sector)] = group.index.to_numpy(dtype=np.int32)

    sector_names = sorted(sector_groups)
    rb_heap: list[tuple[float, tuple[int, int, int, int]]] = []
    nr_heap: list[tuple[float, tuple[int, int, int, int]]] = []
    evaluated = 0

    total_sector_sets = sum(1 for _ in itertools.combinations(sector_names, 4))
    sector_set_no = 0
    for sectors in itertools.combinations(sector_names, 4):
        sector_set_no += 1
        groups = [sector_groups[s] for s in sectors]
        combos = _cartesian_indices(groups)
        for start in range(0, len(combos), CHUNK_SIZE):
            chunk = combos[start:start + CHUNK_SIZE]
            rb, rb_alive, nr, nr_alive = _evaluate_chunk(chunk, factors)

            for local_idx in _local_top(rb, rb_alive):
                _push_top(rb_heap, rb[local_idx], chunk[local_idx])
            for local_idx in _local_top(nr, nr_alive):
                _push_top(nr_heap, nr[local_idx], chunk[local_idx])

            evaluated += len(chunk)
        if sector_set_no % 25 == 0 or sector_set_no == total_sector_sets:
            print(f"Evaluated {evaluated:,} distinct-sector combinations ({sector_set_no}/{total_sector_sets} sector sets).")

    rb_df = _build_output(rb_heap, eligible, factors, months, rebalance=True)
    nr_df = _build_output(nr_heap, eligible, factors, months, rebalance=False)

    if len(rb_df) != TOP_N or len(nr_df) != TOP_N:
        raise RuntimeError(f"Expected {TOP_N} surviving combinations for each strategy; got {len(rb_df)} and {len(nr_df)}.")
    if not (rb_df["Months Funded"] == 120).all() or not (nr_df["Months Funded"] == 120).all():
        raise RuntimeError("A ranked combination failed to fund all 120 actual monthly withdrawals.")

    rb_df.to_csv(REBALANCED_OUT, index=False)
    nr_df.to_csv(NOT_REBALANCED_OUT, index=False)
    print(f"Wrote {REBALANCED_OUT} and {NOT_REBALANCED_OUT}.")
    print(f"#1 rebalanced: {rb_df.iloc[0]['Combo']} -> ${rb_df.iloc[0]['Remaining Balance ($)']:,.2f}")
    print(f"#1 not rebalanced: {nr_df.iloc[0]['Combo']} -> ${nr_df.iloc[0]['Remaining Balance ($)']:,.2f}")


if __name__ == "__main__":
    main()
