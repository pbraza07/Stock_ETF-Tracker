from __future__ import annotations

import argparse
import heapq
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from history_config import rolling_completed_year_labels

SNAPSHOT_FILE = BASE_DIR / "data" / "market_snapshot.csv"
FALLBACK_FILE = BASE_DIR / "data" / "portfolio_combo_source_latest.csv"

TOP200_PROFIT_5Y = BASE_DIR / "data" / "top200_profit_generators_5y.csv"
TOP200_WORST_5Y = BASE_DIR / "data" / "top200_best_worst_year_5y.csv"
TOP200_PROFIT_10Y = BASE_DIR / "data" / "top200_profit_generators_10y.csv"
TOP200_WORST_10Y = BASE_DIR / "data" / "top200_best_worst_year_10y.csv"
TOP100_RB_WITHDRAWAL = BASE_DIR / "data" / "top100_rebalanced_withdrawal_10y.csv"
TOP100_NR_WITHDRAWAL = BASE_DIR / "data" / "top100_not_rebalanced_withdrawal_10y.csv"

START_VALUE = 100_000.0
WITHDRAWAL_START = 300_000.0
ANNUAL_WITHDRAWAL = 85_000.0
TOP200 = 200
TOP100 = 100
CHUNK_SIZE = 100_000


def _source_frame() -> pd.DataFrame:
    for path in (SNAPSHOT_FILE, FALLBACK_FILE):
        if not path.exists():
            continue
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        if df.empty or "Symbol" not in df.columns:
            continue
        if "Type" not in df.columns:
            df["Type"] = "Stock"
        if "Sector" not in df.columns:
            df["Sector"] = "Unknown"
        if "Name" not in df.columns:
            df["Name"] = df["Symbol"]
        df["Symbol"] = df["Symbol"].astype(str).str.upper().str.strip()
        df["Type"] = df["Type"].fillna("").astype(str).str.upper().str.strip()
        df["Sector"] = df["Sector"].fillna("Unknown").astype(str).str.strip()
        df["Name"] = df["Name"].fillna(df["Symbol"]).astype(str).str.strip()
        return df.drop_duplicates("Symbol", keep="last").reset_index(drop=True)
    raise RuntimeError("No MarketScope annual-return source is available.")


def _eligible(frame: pd.DataFrame, years: list[str]) -> pd.DataFrame:
    df = frame.copy()
    for year in years:
        if year not in df.columns:
            raise RuntimeError(f"Annual source is missing completed year {year}.")
        df[year] = pd.to_numeric(df[year], errors="coerce")
    mask = df["Type"].eq("STOCK")
    mask &= ~df["Sector"].str.lower().isin({"", "unknown", "nan", "none"})
    mask &= df[years].notna().all(axis=1)
    out = df.loc[mask].copy().reset_index(drop=True)
    if len(out) < 4 or out["Sector"].nunique() < 4:
        raise RuntimeError(f"Not enough complete-history stocks across four sectors for {len(years)}Y ranking.")
    return out


def _is_current(path: Path, years: list[str], min_rows: int) -> bool:
    if not path.exists():
        return False
    try:
        df = pd.read_csv(path, nrows=max(1, min_rows))
    except Exception:
        return False
    return len(df) >= min_rows and all(year in df.columns for year in years)


def _all_outputs_current() -> bool:
    y5 = rolling_completed_year_labels(5)
    y10 = rolling_completed_year_labels(10)
    checks = [
        (TOP200_PROFIT_5Y, y5, TOP200),
        (TOP200_WORST_5Y, y5, TOP200),
        (TOP200_PROFIT_10Y, y10, TOP200),
        (TOP200_WORST_10Y, y10, TOP200),
        (TOP100_RB_WITHDRAWAL, y10, TOP100),
        (TOP100_NR_WITHDRAWAL, y10, TOP100),
    ]
    return all(_is_current(path, years, rows) for path, years, rows in checks)


def _sector_products(df: pd.DataFrame):
    sector_groups = {
        sector: group.index.to_numpy(dtype=np.int32)
        for sector, group in df.groupby("Sector", sort=True)
        if len(group)
    }
    sectors = sorted(sector_groups)
    for sector_tuple in itertools.combinations(sectors, 4):
        groups = [sector_groups[s] for s in sector_tuple]
        meshes = np.meshgrid(*groups, indexing="ij")
        arrays = [mesh.reshape(-1) for mesh in meshes]
        total = len(arrays[0])
        for start in range(0, total, CHUNK_SIZE):
            end = min(total, start + CHUNK_SIZE)
            yield np.stack([arr[start:end] for arr in arrays], axis=1)


def _push_heap(heap: list, item: tuple, limit: int) -> None:
    if len(heap) < limit:
        heapq.heappush(heap, item)
    elif item > heap[0]:
        heapq.heapreplace(heap, item)


def _local_indices(values: np.ndarray, n: int, valid: np.ndarray | None = None) -> np.ndarray:
    mask = np.isfinite(values) if valid is None else (np.isfinite(values) & valid)
    idx = np.flatnonzero(mask)
    if idx.size <= n:
        return idx
    local = values[idx]
    return idx[np.argpartition(local, -n)[-n:]]


def _evaluate_horizon(df: pd.DataFrame, years: list[str], include_withdrawals: bool):
    returns = df[years].to_numpy(dtype="float64")
    factors = 1.0 + returns / 100.0
    terminal = np.prod(factors, axis=1)

    profit_heap: list[tuple] = []
    worst_heap: list[tuple] = []
    rb_heap: list[tuple] = []
    nr_heap: list[tuple] = []

    combos_seen = 0
    for combo in _sector_products(df):
        combos_seen += len(combo)

        # Buy-and-hold ending value: each stock starts at 25% and is not rebalanced.
        terminal_sum = (
            terminal[combo[:, 0]] + terminal[combo[:, 1]]
            + terminal[combo[:, 2]] + terminal[combo[:, 3]]
        )
        ending = (START_VALUE / 4.0) * terminal_sum

        annual_avg = (
            returns[combo[:, 0]] + returns[combo[:, 1]]
            + returns[combo[:, 2]] + returns[combo[:, 3]]
        ) / 4.0
        worst = np.min(annual_avg, axis=1)

        for idx in _local_indices(ending, TOP200):
            _push_heap(
                profit_heap,
                (float(ending[idx]), tuple(int(x) for x in combo[idx])),
                TOP200,
            )
        # Rank best-worst-year first; ending value is the tie breaker.
        # Encode a tiny normalized ending tie-break in heap ordering separately.
        candidate_idx = _local_indices(worst, TOP200)
        for idx in candidate_idx:
            _push_heap(
                worst_heap,
                (float(worst[idx]), float(ending[idx]), tuple(int(x) for x in combo[idx])),
                TOP200,
            )

        if not include_withdrawals:
            continue

        n = len(combo)
        rb = np.full(n, WITHDRAWAL_START, dtype="float64")
        rb_alive = np.ones(n, dtype=bool)
        nr = np.full((n, 4), WITHDRAWAL_START / 4.0, dtype="float64")
        nr_alive = np.ones(n, dtype=bool)

        # years is newest->oldest; simulations run oldest->newest.
        for yi in range(len(years) - 1, -1, -1):
            stock_rets = np.column_stack([
                returns[combo[:, pos], yi] for pos in range(4)
            ])
            avg = stock_rets.mean(axis=1)

            rb_before = rb * (1.0 + avg / 100.0)
            rb_alive &= rb_before >= ANNUAL_WITHDRAWAL
            rb = np.where(rb_alive, rb_before - ANNUAL_WITHDRAWAL, 0.0)

            nr *= 1.0 + stock_rets / 100.0
            nr_before = nr.sum(axis=1)
            nr_alive &= nr_before >= ANNUAL_WITHDRAWAL
            nr_after = np.where(nr_alive, nr_before - ANNUAL_WITHDRAWAL, 0.0)
            scale = np.divide(
                nr_after, nr_before, out=np.zeros_like(nr_after), where=nr_before > 0
            )
            nr *= scale[:, None]

        rb_idx = _local_indices(rb, TOP100, rb_alive)
        nr_ending = nr.sum(axis=1)
        nr_idx = _local_indices(nr_ending, TOP100, nr_alive)

        for idx in rb_idx:
            _push_heap(
                rb_heap,
                (float(rb[idx]), tuple(int(x) for x in combo[idx])),
                TOP100,
            )
        for idx in nr_idx:
            _push_heap(
                nr_heap,
                (float(nr_ending[idx]), tuple(int(x) for x in combo[idx])),
                TOP100,
            )

    print(f"Evaluated {combos_seen:,} distinct-sector {len(years)}Y combinations.")
    return profit_heap, worst_heap, rb_heap, nr_heap


def _top200_row(df: pd.DataFrame, combo: tuple[int, int, int, int], years: list[str], ranking: str) -> dict:
    rows = df.iloc[list(combo)]
    annual = {year: float(rows[year].mean()) for year in years}
    vals = [(year, annual[year]) for year in years]
    worst_year, worst_value = min(vals, key=lambda x: x[1])
    best_year, best_value = max(vals, key=lambda x: x[1])

    ending = 0.0
    for _, stock in rows.iterrows():
        value = START_VALUE / 4.0
        for year in reversed(years):
            value *= 1.0 + float(stock[year]) / 100.0
        ending += value
    total_return = (ending / START_VALUE - 1.0) * 100.0
    cagr = ((ending / START_VALUE) ** (1.0 / len(years)) - 1.0) * 100.0

    symbols = rows["Symbol"].astype(str).tolist()
    sectors = rows["Sector"].astype(str).tolist()
    row = {
        "Ranking": ranking,
        "Combo": " + ".join(symbols),
    }
    for pos, (symbol, sector) in enumerate(zip(symbols, sectors), start=1):
        row[f"Stock {pos}"] = symbol
        row[f"Sector {pos}"] = sector
    for year in years:
        row[year] = annual[year]
    row.update({
        "Worst Year": worst_year,
        "Worst Year %": worst_value,
        "Best Year": best_year,
        "Best Year %": best_value,
        "Starting Value ($)": START_VALUE,
        "Ending Value ($)": ending,
        "Total Profit ($)": ending - START_VALUE,
        "Total Return %": total_return,
        f"{len(years)}Y CAGR %": cagr,
        "Ranking Start Year": years[-1],
        "Ranking End Year": years[0],
    })
    return row


def _write_top200(df: pd.DataFrame, years: list[str], heap: list, path: Path, ranking: str, worst_mode: bool = False):
    if worst_mode:
        ranked = sorted(heap, key=lambda x: (x[0], x[1]), reverse=True)
        combos = [item[2] for item in ranked[:TOP200]]
    else:
        ranked = sorted(heap, key=lambda x: x[0], reverse=True)
        combos = [item[1] for item in ranked[:TOP200]]
    rows = []
    for rank, combo in enumerate(combos, start=1):
        row = _top200_row(df, combo, years, ranking)
        row["Rank"] = rank
        rows.append(row)
    out = pd.DataFrame(rows)
    first = ["Rank", "Ranking", "Combo"]
    identity = [x for pos in range(1, 5) for x in (f"Stock {pos}", f"Sector {pos}")]
    metrics = [
        *years, "Worst Year", "Worst Year %", "Best Year", "Best Year %",
        "Starting Value ($)", "Ending Value ($)", "Total Profit ($)", "Total Return %",
        f"{len(years)}Y CAGR %", "Ranking Start Year", "Ranking End Year",
    ]
    out = out[first + identity + metrics]
    out.to_csv(path, index=False)
    print(f"Wrote {len(out)} rows -> {path.name}")


def _simulate_withdrawal(df: pd.DataFrame, combo: tuple[int, int, int, int], years: list[str], rebalance: bool) -> dict:
    rows = df.iloc[list(combo)]
    year_balances = {}
    annual_returns = {}
    total_withdrawn = 0.0

    if rebalance:
        balance = WITHDRAWAL_START
        for year in reversed(years):
            pct = float(rows[year].mean())
            annual_returns[year] = pct
            before = balance * (1.0 + pct / 100.0)
            withdrawal = min(ANNUAL_WITHDRAWAL, before)
            balance = max(0.0, before - withdrawal)
            total_withdrawn += withdrawal
            year_balances[year] = balance
        remaining = balance
    else:
        holdings = np.full(4, WITHDRAWAL_START / 4.0, dtype="float64")
        for year in reversed(years):
            start = float(holdings.sum())
            rets = rows[year].to_numpy(dtype="float64") / 100.0
            holdings *= 1.0 + rets
            before = float(holdings.sum())
            annual_returns[year] = ((before / start) - 1.0) * 100.0 if start > 0 else np.nan
            withdrawal = min(ANNUAL_WITHDRAWAL, before)
            remaining = max(0.0, before - withdrawal)
            scale = remaining / before if before > 0 else 0.0
            holdings *= scale
            total_withdrawn += withdrawal
            year_balances[year] = remaining
        remaining = float(holdings.sum())

    vals = [(year, annual_returns[year]) for year in years]
    worst_year, worst_value = min(vals, key=lambda x: x[1])
    best_year, best_value = max(vals, key=lambda x: x[1])
    return {
        "annual_returns": annual_returns,
        "year_balances": year_balances,
        "remaining": remaining,
        "total_withdrawn": total_withdrawn,
        "worst_year": worst_year,
        "worst_value": worst_value,
        "best_year": best_year,
        "best_value": best_value,
    }


def _write_withdrawal(df: pd.DataFrame, years: list[str], heap: list, path: Path, rebalance: bool):
    ranked = sorted(heap, key=lambda x: x[0], reverse=True)[:TOP100]
    strategy = "Rebalanced annually" if rebalance else "Not rebalanced"
    output = []
    for rank, (_, combo) in enumerate(ranked, start=1):
        rows = df.iloc[list(combo)]
        symbols = rows["Symbol"].astype(str).tolist()
        sectors = rows["Sector"].astype(str).tolist()
        names = rows["Name"].astype(str).tolist()
        sim = _simulate_withdrawal(df, combo, years, rebalance)
        row = {"Rank": rank, "Combo": " + ".join(symbols), "Strategy": strategy}
        for pos, (symbol, sector, name) in enumerate(zip(symbols, sectors, names), start=1):
            row[f"Stock {pos}"] = symbol
            row[f"Sector {pos}"] = sector
            row[f"Name {pos}"] = name
        for year in years:
            row[year] = sim["annual_returns"][year]
        row.update({
            "Worst Year": sim["worst_year"],
            "Worst Year %": sim["worst_value"],
            "Best Year": sim["best_year"],
            "Best Year %": sim["best_value"],
            "Starting Value ($)": WITHDRAWAL_START,
            "Annual Withdrawal ($)": ANNUAL_WITHDRAWAL,
            "Total Withdrawn ($)": sim["total_withdrawn"],
            "Remaining Balance ($)": sim["remaining"],
            "Net Value incl. Withdrawals ($)": sim["remaining"] + sim["total_withdrawn"],
            "Net Profit incl. Withdrawals ($)": sim["remaining"] + sim["total_withdrawn"] - WITHDRAWAL_START,
            "Ranking Start Year": years[-1],
            "Ranking End Year": years[0],
        })
        for year in reversed(years):
            row[f"{year} Balance After Withdrawal ($)"] = sim["year_balances"][year]
        output.append(row)
    pd.DataFrame(output).to_csv(path, index=False)
    print(f"Wrote {len(output)} rows -> {path.name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Rebuild even when all output files already cover the latest completed year.")
    args = parser.parse_args()

    if not args.force and _all_outputs_current():
        print("Dynamic annual ranking files already cover the latest completed 5Y/10Y windows; no rebuild required.")
        return

    source = _source_frame()

    years5 = rolling_completed_year_labels(5)
    df5 = _eligible(source, years5)
    p5, w5, _, _ = _evaluate_horizon(df5, years5, include_withdrawals=False)
    _write_top200(df5, years5, p5, TOP200_PROFIT_5Y, "Best Profit Generator")
    _write_top200(df5, years5, w5, TOP200_WORST_5Y, "Best Worst Year", worst_mode=True)

    years10 = rolling_completed_year_labels(10)
    df10 = _eligible(source, years10)
    p10, w10, rb, nr = _evaluate_horizon(df10, years10, include_withdrawals=True)
    _write_top200(df10, years10, p10, TOP200_PROFIT_10Y, "Best Profit Generator")
    _write_top200(df10, years10, w10, TOP200_WORST_10Y, "Best Worst Year", worst_mode=True)
    _write_withdrawal(df10, years10, rb, TOP100_RB_WITHDRAWAL, rebalance=True)
    _write_withdrawal(df10, years10, nr, TOP100_NR_WITHDRAWAL, rebalance=False)


if __name__ == "__main__":
    main()
