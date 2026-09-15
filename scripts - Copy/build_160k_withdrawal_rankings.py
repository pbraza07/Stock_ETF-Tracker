from __future__ import annotations

import csv
import itertools
import math
from collections import Counter
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).resolve().parents[1]
SOURCE = BASE_DIR / "data" / "annual_performance_160k_source.csv"
OUT_RB = BASE_DIR / "data" / "top100_rebalanced_withdrawal_10y_160k_max5.csv"
OUT_NR = BASE_DIR / "data" / "top100_not_rebalanced_withdrawal_10y_160k_max5.csv"

START_VALUE = 300_000.0
ANNUAL_WITHDRAWAL = 160_000.0
TOP_N = 100
MAX_TICKER_USES = 5
CHUNK_SIZE = 180_000


def _number(value):
    text = str(value or "").strip().replace("%", "").replace("$", "").replace(",", "")
    if text in {"", "—", "-", "None", "nan", "N/A"}:
        return None
    try:
        result = float(text)
    except Exception:
        return None
    return result if math.isfinite(result) else None


def _year_columns(fieldnames: list[str]) -> list[str]:
    years = sorted(
        [str(col) for col in fieldnames if str(col).isdigit() and len(str(col)) == 4],
        reverse=True,
    )
    if len(years) < 10:
        raise RuntimeError("Annual-performance source must contain at least ten completed calendar-year columns.")
    return years[:10]


def _load_source():
    if not SOURCE.exists():
        raise RuntimeError(f"Missing ranking source: {SOURCE}")
    with SOURCE.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        years = _year_columns(fieldnames)
        stocks = []
        for raw in reader:
            if str(raw.get("Type") or "").strip().upper() != "STOCK":
                continue
            symbol = str(raw.get("Symbol") or "").strip().upper()
            sector = str(raw.get("Sector") or "").strip()
            if not symbol or not sector or sector.lower() in {"", "unknown", "none", "nan"}:
                continue
            annual = [_number(raw.get(year)) for year in years]
            if any(value is None for value in annual):
                continue
            stocks.append(
                {
                    "Symbol": symbol,
                    "Name": str(raw.get("Name") or "").strip() or symbol,
                    "Sector": sector,
                    "returns": annual,
                }
            )
    if len(stocks) < 4:
        raise RuntimeError("Not enough complete-history stocks in ranking source.")
    if len({row["Sector"] for row in stocks}) < 4:
        raise RuntimeError("Ranking source needs at least four sectors.")
    return stocks, years


def _composite_score(funded: np.ndarray, total_withdrawn: np.ndarray, remaining: np.ndarray) -> np.ndarray:
    # Income delivery is the primary objective:
    # 1) full $160K withdrawals funded;
    # 2) total cash actually delivered;
    # 3) ending portfolio balance.
    return funded.astype(np.float64) * 1e12 + total_withdrawn * 1e3 + remaining / 1e6


def _enumerate_scores(stocks, years):
    returns = np.asarray([row["returns"] for row in stocks], dtype=np.float64)
    sector_groups = {}
    for index, row in enumerate(stocks):
        sector_groups.setdefault(row["Sector"], []).append(index)
    sector_groups = {
        sector: np.asarray(indices, dtype=np.uint8)
        for sector, indices in sector_groups.items()
    }
    sectors = sorted(sector_groups)
    total_combos = sum(
        len(sector_groups[a]) * len(sector_groups[b]) * len(sector_groups[c]) * len(sector_groups[d])
        for a, b, c, d in itertools.combinations(sectors, 4)
    )
    combos = np.empty((total_combos, 4), dtype=np.uint8)
    rb_scores = np.empty(total_combos, dtype=np.float64)
    nr_scores = np.empty(total_combos, dtype=np.float64)

    cursor = 0
    for sector_tuple in itertools.combinations(sectors, 4):
        groups = [sector_groups[sector] for sector in sector_tuple]
        meshes = np.meshgrid(*groups, indexing="ij")
        flattened = [mesh.reshape(-1) for mesh in meshes]
        total = len(flattened[0])

        for start in range(0, total, CHUNK_SIZE):
            end = min(total, start + CHUNK_SIZE)
            combo = np.stack([array[start:end] for array in flattened], axis=1).astype(np.uint8, copy=False)
            count = len(combo)

            # Rebalanced annually: each year starts at equal 25% weights.
            balance = np.full(count, START_VALUE, dtype=np.float64)
            funded = np.zeros(count, dtype=np.uint8)
            total_withdrawn = np.zeros(count, dtype=np.float64)
            active = np.ones(count, dtype=bool)
            for year_index in range(len(years) - 1, -1, -1):
                avg = (
                    returns[combo[:, 0], year_index]
                    + returns[combo[:, 1], year_index]
                    + returns[combo[:, 2], year_index]
                    + returns[combo[:, 3], year_index]
                ) / 4.0
                before = balance * (1.0 + avg / 100.0)
                actual = np.minimum(ANNUAL_WITHDRAWAL, np.maximum(before, 0.0))
                funded += (active & (before >= ANNUAL_WITHDRAWAL - 0.005)).astype(np.uint8)
                total_withdrawn += np.where(active, actual, 0.0)
                balance = np.where(active, np.maximum(0.0, before - actual), 0.0)
                active &= balance > 0.0
            rb = _composite_score(funded, total_withdrawn, balance)

            # Not rebalanced: holdings retain drift; withdrawals are proportional.
            holdings = np.full((count, 4), START_VALUE / 4.0, dtype=np.float64)
            funded_nr = np.zeros(count, dtype=np.uint8)
            total_withdrawn_nr = np.zeros(count, dtype=np.float64)
            active_nr = np.ones(count, dtype=bool)
            for year_index in range(len(years) - 1, -1, -1):
                holdings *= 1.0 + returns[combo, year_index] / 100.0
                before = holdings.sum(axis=1)
                actual = np.minimum(ANNUAL_WITHDRAWAL, np.maximum(before, 0.0))
                funded_nr += (active_nr & (before >= ANNUAL_WITHDRAWAL - 0.005)).astype(np.uint8)
                total_withdrawn_nr += np.where(active_nr, actual, 0.0)
                after = np.where(active_nr, np.maximum(0.0, before - actual), 0.0)
                scale = np.divide(after, before, out=np.zeros_like(after), where=before > 0)
                holdings *= scale[:, None]
                active_nr &= after > 0.0
            nr_remaining = holdings.sum(axis=1)
            nr = _composite_score(funded_nr, total_withdrawn_nr, nr_remaining)

            combos[cursor : cursor + count] = combo
            rb_scores[cursor : cursor + count] = rb
            nr_scores[cursor : cursor + count] = nr
            cursor += count

    return returns, combos, rb_scores, nr_scores


def _select_top100(scores, combos, stocks):
    order = np.argsort(scores)[::-1]
    uses = Counter()
    selected = []
    for index in order:
        combo = tuple(int(value) for value in combos[index])
        symbols = [stocks[i]["Symbol"] for i in combo]
        if any(uses[symbol] >= MAX_TICKER_USES for symbol in symbols):
            continue
        selected.append((int(index), combo))
        uses.update(symbols)
        if len(selected) == TOP_N:
            break
    if len(selected) != TOP_N:
        raise RuntimeError(
            f"Could only build {len(selected)} diversified combinations under max-{MAX_TICKER_USES} rule."
        )
    return selected, uses


def _simulate(combo, returns, years, rebalance):
    combo_array = np.asarray(combo, dtype=int)
    annual_returns = {}
    balances_after = {}
    total_withdrawn = 0.0
    funded = 0
    depleted_year = ""

    if rebalance:
        balance = START_VALUE
        for year_index in range(len(years) - 1, -1, -1):
            year = years[year_index]
            pct = float(np.mean(returns[combo_array, year_index]))
            annual_returns[year] = pct
            before = balance * (1.0 + pct / 100.0)
            actual = min(ANNUAL_WITHDRAWAL, max(before, 0.0))
            if before >= ANNUAL_WITHDRAWAL - 0.005:
                funded += 1
            elif not depleted_year:
                depleted_year = year
            total_withdrawn += actual
            balance = max(0.0, before - actual)
            balances_after[year] = balance
            if balance <= 0:
                for later_index in range(year_index - 1, -1, -1):
                    later_year = years[later_index]
                    annual_returns[later_year] = float(np.mean(returns[combo_array, later_index]))
                    balances_after[later_year] = 0.0
                break
        remaining = balance
    else:
        holdings = np.full(4, START_VALUE / 4.0, dtype=np.float64)
        for year_index in range(len(years) - 1, -1, -1):
            year = years[year_index]
            start_balance = float(holdings.sum())
            holdings *= 1.0 + returns[combo_array, year_index] / 100.0
            before = float(holdings.sum())
            pct = ((before / start_balance) - 1.0) * 100.0 if start_balance > 0 else 0.0
            annual_returns[year] = pct
            actual = min(ANNUAL_WITHDRAWAL, max(before, 0.0))
            if before >= ANNUAL_WITHDRAWAL - 0.005:
                funded += 1
            elif not depleted_year:
                depleted_year = year
            total_withdrawn += actual
            after = max(0.0, before - actual)
            holdings *= after / before if before > 0 else 0.0
            balances_after[year] = after
            if after <= 0:
                for later_index in range(year_index - 1, -1, -1):
                    later_year = years[later_index]
                    annual_returns[later_year] = 0.0
                    balances_after[later_year] = 0.0
                break
        remaining = float(holdings.sum())

    annual_pairs = [(year, annual_returns.get(year, 0.0)) for year in years]
    worst_year, worst_pct = min(annual_pairs, key=lambda item: item[1])
    best_year, best_pct = max(annual_pairs, key=lambda item: item[1])
    return {
        "annual_returns": annual_returns,
        "balances_after": balances_after,
        "funded": funded,
        "depleted_year": depleted_year,
        "total_withdrawn": total_withdrawn,
        "remaining": remaining,
        "worst_year": worst_year,
        "worst_pct": worst_pct,
        "best_year": best_year,
        "best_pct": best_pct,
    }


def _write_output(selected, uses, stocks, returns, years, rebalance, path):
    distinct = len(uses)
    output = []
    for rank, (_, combo) in enumerate(selected, start=1):
        detail = _simulate(combo, returns, years, rebalance)
        symbols = [stocks[i]["Symbol"] for i in combo]
        row = {
            "Rank": rank,
            "Combo": " + ".join(symbols),
            "Strategy": "Rebalanced annually" if rebalance else "Not rebalanced",
        }
        for position, index in enumerate(combo, start=1):
            stock = stocks[index]
            row[f"Stock {position}"] = stock["Symbol"]
            row[f"Sector {position}"] = stock["Sector"]
            row[f"Name {position}"] = stock["Name"]
            row[f"Stock {position} Top100 Uses"] = uses[stock["Symbol"]]

        for year in years:
            row[year] = detail["annual_returns"].get(year, 0.0)

        row.update(
            {
                "Worst Year": detail["worst_year"],
                "Worst Year %": detail["worst_pct"],
                "Best Year": detail["best_year"],
                "Best Year %": detail["best_pct"],
                "Starting Value ($)": START_VALUE,
                "Annual Withdrawal ($)": ANNUAL_WITHDRAWAL,
                "Target Withdrawals": len(years),
                "Withdrawals Fully Funded": detail["funded"],
                "Full 10Y Withdrawal Goal": "Yes" if detail["funded"] == len(years) else "No",
                "Depleted Year": detail["depleted_year"],
                "Total Withdrawn ($)": detail["total_withdrawn"],
                "Remaining Balance ($)": detail["remaining"],
                "Net Value incl. Withdrawals ($)": detail["remaining"] + detail["total_withdrawn"],
                "Net Profit incl. Withdrawals ($)": detail["remaining"] + detail["total_withdrawn"] - START_VALUE,
                "Max Ticker Repeats": MAX_TICKER_USES,
                "Distinct Tickers in Top 100": distinct,
                "Ranking Window Start": years[-1],
                "Ranking Window End": years[0],
                "Ranking Source": SOURCE.name,
                "Ranking Method": (
                    "Rank by full withdrawals funded, then total cash delivered, then ending balance; "
                    "greedily enforce max 5 Top-100 appearances per ticker."
                ),
            }
        )
        for year in sorted(years):
            row[f"{year} Balance After Withdrawal ($)"] = detail["balances_after"].get(year, 0.0)
        output.append(row)

    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(output[0].keys()))
        writer.writeheader()
        writer.writerows(output)

    print(
        f"Wrote {len(output)} rows to {path.name}; "
        f"{len(uses)} distinct tickers; max ticker use {max(uses.values())}; "
        f"full 10Y goal rows {sum(row['Full 10Y Withdrawal Goal'] == 'Yes' for row in output)}."
    )


def main():
    stocks, years = _load_source()
    returns, combos, rb_scores, nr_scores = _enumerate_scores(stocks, years)
    rb_selected, rb_uses = _select_top100(rb_scores, combos, stocks)
    nr_selected, nr_uses = _select_top100(nr_scores, combos, stocks)
    _write_output(rb_selected, rb_uses, stocks, returns, years, True, OUT_RB)
    _write_output(nr_selected, nr_uses, stocks, returns, years, False, OUT_NR)


if __name__ == "__main__":
    main()
