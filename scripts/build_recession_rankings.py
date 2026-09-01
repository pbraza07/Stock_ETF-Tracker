from __future__ import annotations

import itertools
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
SNAPSHOT_FILE = BASE_DIR / "data" / "market_snapshot.csv"
FALLBACK_FILE = BASE_DIR / "data" / "portfolio_combo_source_latest.csv"
REBALANCED_OUT = BASE_DIR / "data" / "top100_recession_balanced_rebalanced_10y.csv"
NOT_REBALANCED_OUT = BASE_DIR / "data" / "top100_recession_balanced_not_rebalanced_10y.csv"

STARTING_VALUE = 300_000.0
TOP_N = 100
MAX_TICKER_REPEATS = 5
SIM_YEARS = [str(y) for y in range(2016, 2026)]
RECESSION_STRESS_YEARS = ["2001", "2008", "2009", "2020"]
NBER_SOURCE = "https://www.nber.org/research/data/us-business-cycle-expansions-and-contractions"
NBER_PERIODS = "Mar-Nov 2001; Dec 2007-Jun 2009; Feb-Apr 2020"

# v5.9.52: the old 20/20 role pools were too concentrated to support a
# 5-appearance ceiling across 100 four-stock portfolios. Broaden the role pools
# substantially, then apply the hard ticker-usage constraint after ranking.
PROFIT_POOL_SIZE = 100
DEFENSE_POOL_SIZE = 100
CANDIDATES_PER_PROFIT_PAIR = 250


def _source_frame() -> pd.DataFrame:
    for path in (SNAPSHOT_FILE, FALLBACK_FILE):
        if not path.exists():
            continue
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        if df.empty:
            continue
        if "Symbol" not in df.columns and "Stock" in df.columns:
            df = df.rename(columns={"Stock": "Symbol"})
        if "Name" not in df.columns:
            df["Name"] = df["Symbol"]
        if "Sector" not in df.columns:
            # MarketScope exports may use Industry as the best available category.
            df["Sector"] = df.get("Industry", "Unknown")
        if "Type" not in df.columns:
            df["Type"] = "Stock"
        df["Symbol"] = df["Symbol"].astype(str).str.upper().str.strip()
        df["Sector"] = df["Sector"].fillna("Unknown").astype(str).str.strip()
        df["Name"] = df["Name"].fillna(df["Symbol"]).astype(str).str.strip()
        df["Type"] = df["Type"].fillna("").astype(str).str.upper().str.strip()
        return df.drop_duplicates("Symbol", keep="last").reset_index(drop=True)
    raise RuntimeError("No MarketScope annual-return source file is available.")


def _numeric_years(df: pd.DataFrame) -> list[str]:
    cols = [str(c) for c in df.columns if str(c).isdigit() and len(str(c)) == 4]
    return sorted(cols, key=int)


def _compound(values: list[float]) -> float:
    value = 1.0
    for r in values:
        if not np.isfinite(r) or r <= -100.0:
            return np.nan
        value *= 1.0 + r / 100.0
    return value - 1.0


def _candidate_scores(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    annual_cols = _numeric_years(df)
    for col in annual_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    mask = df["Type"].eq("STOCK") & ~df["Sector"].str.lower().isin({"", "unknown", "nan", "none"})
    mask &= df[SIM_YEARS].notna().all(axis=1)
    eligible = df.loc[mask].copy()
    if eligible.empty:
        raise RuntimeError("No stocks have complete 2016-2025 annual returns.")

    # Profit engines: strong full-10Y compounding and a repeated history of
    # profitable calendar years. Keep a broad pool so the final Top 100 can be
    # genuinely diversified under the max-five ticker rule.
    profit_rows = []
    for idx, row in eligible.iterrows():
        vals = [float(row[y]) for y in SIM_YEARS]
        growth = _compound(vals)
        if not np.isfinite(growth):
            continue
        positive = sum(v > 0 for v in vals)
        worst = min(vals)
        cagr = (1.0 + growth) ** (1.0 / len(vals)) - 1.0 if growth > -1 else np.nan
        if positive < 6 or not np.isfinite(cagr) or cagr <= 0:
            continue
        profit_rows.append((idx, growth, cagr, positive, worst))
    profit_score = pd.DataFrame(profit_rows, columns=["idx", "growth", "cagr", "positive", "worst"])
    profit_score = profit_score.sort_values(
        ["growth", "positive", "worst"], ascending=[False, False, False]
    ).head(PROFIT_POOL_SIZE)
    profit = eligible.loc[profit_score["idx"].tolist()].copy()
    profit["Role Score"] = profit_score.set_index("idx").reindex(profit.index)["growth"]
    profit["Profit CAGR %"] = profit_score.set_index("idx").reindex(profit.index)["cagr"] * 100.0
    profit["Profit Positive Years"] = profit_score.set_index("idx").reindex(profit.index)["positive"]
    profit["Role"] = "Profit Engine"

    # Recession defense: use official NBER recession periods represented by
    # the annual dataset. Rank maximin first, then average stress return.
    stress_years = [y for y in RECESSION_STRESS_YEARS if y in eligible.columns]
    defense_rows = []
    for idx, row in eligible.iterrows():
        vals = [float(row[y]) for y in stress_years if pd.notna(row.get(y))]
        if len(vals) < 2:
            continue
        worst = min(vals)
        avg = float(np.mean(vals))
        positive = sum(v > 0 for v in vals)
        defense_rows.append((idx, worst, avg, positive, len(vals)))
    defense_score = pd.DataFrame(
        defense_rows, columns=["idx", "worst", "avg", "positive", "count"]
    )
    defense_score = defense_score.sort_values(
        ["worst", "avg", "positive"], ascending=[False, False, False]
    ).head(DEFENSE_POOL_SIZE)
    defense = eligible.loc[defense_score["idx"].tolist()].copy()
    defense["Recession Worst %"] = defense_score.set_index("idx").reindex(defense.index)["worst"]
    defense["Recession Avg %"] = defense_score.set_index("idx").reindex(defense.index)["avg"]
    defense["Recession Positive Years"] = defense_score.set_index("idx").reindex(defense.index)["positive"]
    defense["Recession Observations"] = defense_score.set_index("idx").reindex(defense.index)["count"]
    defense["Role"] = "Recession Defense"
    return profit, defense, stress_years


def _stock_terminal_factor(row: pd.Series) -> float:
    factor = 1.0
    for year in SIM_YEARS:
        factor *= 1.0 + float(row[year]) / 100.0
    return factor


def _role_pairs(frame: pd.DataFrame, role_frame: pd.DataFrame, stress_years: list[str]) -> list[dict]:
    """Precompute all same-role pairs from different sectors."""
    pairs: list[dict] = []
    idxs = list(role_frame.index)
    for i1, i2 in itertools.combinations(idxs, 2):
        sector1 = str(frame.loc[i1, "Sector"])
        sector2 = str(frame.loc[i2, "Sector"])
        if sector1 == sector2:
            continue
        annual_sum = np.array(
            [float(frame.loc[i1, y]) + float(frame.loc[i2, y]) for y in SIM_YEARS],
            dtype="float64",
        )
        terminal_sum = _stock_terminal_factor(frame.loc[i1]) + _stock_terminal_factor(frame.loc[i2])
        stress_values = []
        for year in stress_years:
            vals = pd.to_numeric(frame.loc[[i1, i2], year], errors="coerce").dropna()
            if len(vals) == 2:
                stress_values.append(float(vals.mean()))
        pairs.append(
            {
                "indices": (int(i1), int(i2)),
                "symbols": (str(frame.loc[i1, "Symbol"]), str(frame.loc[i2, "Symbol"])),
                "sectors": (sector1, sector2),
                "annual_sum": annual_sum,
                "terminal_sum": float(terminal_sum),
                "recession_worst": min(stress_values) if stress_values else np.nan,
                "recession_avg": float(np.mean(stress_values)) if stress_values else np.nan,
                "recession_positive": sum(v > 0 for v in stress_values),
                "recession_obs": len(stress_values),
            }
        )
    return pairs


def _candidate_pool(
    frame: pd.DataFrame,
    profit_pairs: list[dict],
    defense_pairs: list[dict],
    rebalanced: bool,
    keep_per_profit_pair: int,
) -> list[tuple]:
    """Build a broad high-profit candidate pool before the diversity constraint.

    For every Profit Engine pair, retain its best compatible Recession Defense
    partners. This preserves broad Profit Engine coverage while still favoring
    the highest-profit four-stock portfolios.
    """
    d_annual = np.stack([p["annual_sum"] for p in defense_pairs], axis=0)
    d_terminal = np.array([p["terminal_sum"] for p in defense_pairs], dtype="float64")
    candidates: list[tuple] = []

    for pp in profit_pairs:
        p_indices = set(pp["indices"])
        p_sectors = set(pp["sectors"])

        valid = np.fromiter(
            (
                not p_indices.intersection(dp["indices"])
                and not p_sectors.intersection(dp["sectors"])
                and dp["recession_obs"] >= 2
                for dp in defense_pairs
            ),
            dtype=bool,
            count=len(defense_pairs),
        )
        valid_idx = np.flatnonzero(valid)
        if valid_idx.size == 0:
            continue

        if rebalanced:
            factors = 1.0 + (d_annual[valid_idx] + pp["annual_sum"][None, :]) / 400.0
            good = np.all(np.isfinite(factors) & (factors >= 0.0), axis=1)
            valid_idx = valid_idx[good]
            if valid_idx.size == 0:
                continue
            scores = STARTING_VALUE * np.prod(
                1.0 + (d_annual[valid_idx] + pp["annual_sum"][None, :]) / 400.0,
                axis=1,
            )
        else:
            scores = (STARTING_VALUE / 4.0) * (d_terminal[valid_idx] + pp["terminal_sum"])

        take = min(int(keep_per_profit_pair), len(valid_idx))
        if take <= 0:
            continue
        if take < len(valid_idx):
            local = np.argpartition(scores, -take)[-take:]
            chosen_idx = valid_idx[local]
            chosen_scores = scores[local]
        else:
            chosen_idx = valid_idx
            chosen_scores = scores

        order = np.argsort(chosen_scores)[::-1]
        for pos in order:
            dp = defense_pairs[int(chosen_idx[pos])]
            combo = pp["indices"] + dp["indices"]
            symbols = pp["symbols"] + dp["symbols"]
            candidates.append(
                (
                    float(chosen_scores[pos]),
                    float(dp["recession_worst"]),
                    float(dp["recession_avg"]),
                    int(dp["recession_positive"]),
                    int(dp["recession_obs"]),
                    combo,
                    symbols,
                )
            )

    # Same four stocks can qualify under multiple role assignments. Keep the
    # highest-ranked role assignment for that four-stock set.
    candidates.sort(key=lambda x: (x[0], x[1], x[2], x[3]), reverse=True)
    deduped = []
    seen = set()
    for item in candidates:
        key = tuple(sorted(item[6]))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _select_diversified_top100(candidates: list[tuple]) -> tuple[list[tuple], Counter]:
    """Greedily rank by profit while enforcing max five appearances per ticker."""
    usage: Counter = Counter()
    selected: list[tuple] = []
    for item in candidates:
        symbols = item[6]
        if any(usage[s] >= MAX_TICKER_REPEATS for s in symbols):
            continue
        selected.append(item)
        for s in symbols:
            usage[s] += 1
        if len(selected) >= TOP_N:
            break
    return selected, usage


def _simulate(indices: tuple[int, int, int, int], frame: pd.DataFrame, rebalance: bool) -> dict:
    rows = frame.loc[list(indices)]
    annual_returns = {}
    year_balances = {}
    if rebalance:
        balance = STARTING_VALUE
        for year in SIM_YEARS:
            year_ret = float(rows[year].mean())
            annual_returns[year] = year_ret
            balance *= 1.0 + year_ret / 100.0
            year_balances[year] = balance
        ending = balance
    else:
        holdings = np.full(4, STARTING_VALUE / 4.0, dtype="float64")
        for year in SIM_YEARS:
            start = float(holdings.sum())
            rets = rows[year].to_numpy(dtype="float64") / 100.0
            holdings *= 1.0 + rets
            ending_year = float(holdings.sum())
            annual_returns[year] = ((ending_year / start) - 1.0) * 100.0 if start > 0 else np.nan
            year_balances[year] = ending_year
        ending = float(holdings.sum())
    vals = [annual_returns[y] for y in SIM_YEARS]
    worst_i = int(np.nanargmin(vals))
    best_i = int(np.nanargmax(vals))
    return {
        "ending": ending,
        "annual_returns": annual_returns,
        "year_balances": year_balances,
        "worst_year": SIM_YEARS[worst_i],
        "worst_pct": vals[worst_i],
        "best_year": SIM_YEARS[best_i],
        "best_pct": vals[best_i],
    }


def _build(
    strategy_rebalanced: bool,
    frame: pd.DataFrame,
    profit: pd.DataFrame,
    defense: pd.DataFrame,
    stress_years: list[str],
) -> pd.DataFrame:
    profit_pairs = _role_pairs(frame, profit, stress_years)
    defense_pairs = _role_pairs(frame, defense, stress_years)

    # Start with a broad per-profit-pair candidate set. If the hard five-use
    # ceiling cannot fill all 100 portfolios, automatically widen it.
    selected: list[tuple] = []
    usage: Counter = Counter()
    used_keep = CANDIDATES_PER_PROFIT_PAIR
    for keep in (CANDIDATES_PER_PROFIT_PAIR, 500, 1000, len(defense_pairs)):
        pool = _candidate_pool(
            frame,
            profit_pairs,
            defense_pairs,
            rebalanced=strategy_rebalanced,
            keep_per_profit_pair=keep,
        )
        selected, usage = _select_diversified_top100(pool)
        used_keep = keep
        if len(selected) >= TOP_N:
            break

    if len(selected) < TOP_N:
        raise RuntimeError(
            f"Could only build {len(selected)} diversified portfolios with "
            f"MAX_TICKER_REPEATS={MAX_TICKER_REPEATS}."
        )

    # Hard QA: 100 portfolios x 4 stocks and no ticker above the requested cap.
    assert len(selected) == TOP_N
    assert max(usage.values()) <= MAX_TICKER_REPEATS

    rows = []
    strategy = "Rebalanced annually" if strategy_rebalanced else "Not rebalanced"
    distinct_tickers = len(usage)
    for rank, item in enumerate(selected, 1):
        _, rec_worst, rec_avg, rec_positive, rec_obs, combo, symbols = item
        sim = _simulate(combo, frame, strategy_rebalanced)
        row = {
            "Rank": rank,
            "Combo": " + ".join(symbols),
            "Strategy": strategy,
        }
        for pos, i in enumerate(combo, 1):
            role = "Profit Engine" if pos <= 2 else "Recession Defense"
            symbol = str(frame.loc[i, "Symbol"])
            row[f"Stock {pos}"] = symbol
            row[f"Sector {pos}"] = str(frame.loc[i, "Sector"])
            row[f"Name {pos}"] = str(frame.loc[i, "Name"])
            row[f"Role {pos}"] = role
            row[f"Stock {pos} Top100 Uses"] = int(usage[symbol])

        for year in reversed(SIM_YEARS):
            row[year] = sim["annual_returns"][year]
        row.update(
            {
                "Worst Year": sim["worst_year"],
                "Worst Year %": sim["worst_pct"],
                "Best Year": sim["best_year"],
                "Best Year %": sim["best_pct"],
                "Defense Recession Worst %": rec_worst,
                "Defense Recession Avg %": rec_avg,
                "Defense Recession Positive Years": rec_positive,
                "Defense Recession Observations": rec_obs,
                "Recession Stress Years": ",".join(stress_years),
                "Starting Value ($)": STARTING_VALUE,
                "Annual Withdrawal ($)": 0.0,
                "Total Withdrawn ($)": 0.0,
                "Remaining Balance ($)": sim["ending"],
                "Net Value incl. Withdrawals ($)": sim["ending"],
                "Net Profit incl. Withdrawals ($)": sim["ending"] - STARTING_VALUE,
                "Max Ticker Repeats": MAX_TICKER_REPEATS,
                "Distinct Tickers in Top 100": distinct_tickers,
                "Candidate Partners per Profit Pair": int(used_keep),
                "NBER Recession Periods": NBER_PERIODS,
                "NBER Source": NBER_SOURCE,
            }
        )
        for year in SIM_YEARS:
            row[f"{year} Balance After Withdrawal ($)"] = sim["year_balances"][year]
        rows.append(row)

    result = pd.DataFrame(rows)
    # Final file-level QA.
    all_symbols = []
    for pos in range(1, 5):
        all_symbols.extend(result[f"Stock {pos}"].astype(str).tolist())
    observed = Counter(all_symbols)
    if max(observed.values()) > MAX_TICKER_REPEATS:
        raise RuntimeError(f"Ticker repeat cap violated: {observed.most_common(5)}")
    return result


def main() -> None:
    raw = _source_frame()
    profit, defense, stress_years = _candidate_scores(raw)
    eligible = raw.copy()

    rb = _build(True, eligible, profit, defense, stress_years)
    nr = _build(False, eligible, profit, defense, stress_years)

    if len(rb) < TOP_N or len(nr) < TOP_N:
        raise RuntimeError(f"Expected {TOP_N} recession-balanced combinations, got {len(rb)} and {len(nr)}.")

    rb.to_csv(REBALANCED_OUT, index=False)
    nr.to_csv(NOT_REBALANCED_OUT, index=False)

    def summary(df: pd.DataFrame) -> tuple[int, int]:
        counts = Counter()
        for pos in range(1, 5):
            counts.update(df[f"Stock {pos}"].astype(str))
        return len(counts), max(counts.values())

    rb_distinct, rb_max = summary(rb)
    nr_distinct, nr_max = summary(nr)

    print(
        f"Profit engines considered: {len(profit)}; recession defenses: {len(defense)}; "
        f"stress years: {stress_years}; max ticker repeats: {MAX_TICKER_REPEATS}"
    )
    print(
        f"Rebalanced #1: {rb.iloc[0]['Combo']} -> ${rb.iloc[0]['Remaining Balance ($)']:,.2f}; "
        f"{rb_distinct} distinct tickers; max use {rb_max}"
    )
    print(
        f"Not rebalanced #1: {nr.iloc[0]['Combo']} -> ${nr.iloc[0]['Remaining Balance ($)']:,.2f}; "
        f"{nr_distinct} distinct tickers; max use {nr_max}"
    )


if __name__ == "__main__":
    main()
