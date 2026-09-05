"""Auditable full-universe stock selection using governed projection assumptions."""

from datetime import datetime, timezone
from copy import deepcopy
import numpy as np
import pandas as pd
from favorite_picks import (
    screen_favorite_candidates,
    _percentile_rank,
    _geometric_return,
)
from future_projection import prepare_projection_model, _monthly_maps
from future_projection_live import (
    build_current_market_state,
    condition_model_assumptions,
    walk_forward_validate,
)
from top12_simulation import project_candidates

PERCENTILES = (10, 25, 50, 75, 90)
STRESS = (
    ("2007-10", "2009-03"),
    ("2011-05", "2011-10"),
    ("2018-10", "2018-12"),
    ("2020-02", "2020-03"),
    ("2022-01", "2022-10"),
)
WEIGHTS = {
    "Recession": {
        "Defense": 0.30,
        "Drawdown": 0.20,
        "Recovery": 0.15,
        "Bear Model": 0.15,
        "Consistency": 0.10,
        "Current Strength": 0.05,
        "Profitability": 0.05,
    },
    "Max Profit": {
        "Historical Performance": 0.25,
        "Recent Performance": 0.15,
        "Future P50": 0.20,
        "Future P75": 0.15,
        "Fundamentals": 0.10,
        "Consistency": 0.05,
        "Relative Strength": 0.05,
        "Downside Quality": 0.05,
    },
}
SECTOR_ALIASES = {
    "Financial Services": "Finance",
    "Financials": "Finance",
    "Healthcare": "Health Care",
    "Consumer Cyclical": "Consumer Discretionary",
    "Consumer Defensive": "Consumer Staples",
    "Communication Services": "Telecommunications",
    "Materials": "Basic Materials",
}


def stress_evidence(hist, annual, market_history, sector_histories):
    """Observed monthly event evidence; coarse annual windows stay explicit."""
    events = []
    for start, end in STRESS:
        monthly = len(hist) >= 24
        labels = (
            [str(p) for p in pd.period_range(start, end, freq="M")]
            if monthly
            else [str(y) for y in range(int(start[:4]), int(end[:4]) + 1)]
        )
        series = hist if monthly else annual
        if not all(label in series.index for label in labels):
            continue
        window = series.loc[labels]
        total = float(np.prod(1 + window) - 1) * 100
        drawdown, _ = path_metrics(window)
        event = {
            "start": start,
            "end": end,
            "basis": "Monthly observed" if monthly else "Annual approximation",
            "return_pct": total,
            "drawdown_pct": drawdown,
        }
        if monthly:
            event["negative_months"] = int((window < 0).sum())
            event["downside_volatility_pct"] = float(
                np.sqrt(np.mean(np.minimum(window, 0) ** 2)) * np.sqrt(12) * 100
            )
            peer_returns = []
            for peer in sector_histories:
                if all(label in peer.index for label in labels):
                    peer_returns.append(float(np.prod(1 + peer.loc[labels]) - 1) * 100)
            event["sector_excess_pct"] = (
                total - float(np.median(peer_returns)) if peer_returns else np.nan
            )
            event["market_excess_pct"] = (
                total - float(np.prod(1 + market_history.loc[labels]) - 1) * 100
                if all(label in market_history.index for label in labels)
                else np.nan
            )
            trough = window.index[int(np.argmin(np.cumprod(1 + window)))]
            for months in (6, 12):
                forward = [
                    str(p)
                    for p in pd.period_range(
                        pd.Period(trough, freq="M") + 1, periods=months, freq="M"
                    )
                ]
                event[f"post_trough_{months}m_pct"] = (
                    float(np.prod(1 + hist.loc[forward]) - 1) * 100
                    if all(p in hist.index for p in forward)
                    else np.nan
                )
        events.append(event)

    def mean(key):
        values = [e[key] for e in events if key in e and np.isfinite(e[key])]
        return float(np.mean(values)) if values else np.nan

    return {
        "Stress Events": len(events),
        "Stress Evidence Basis": (
            "Monthly observed" if len(hist) >= 24 else "Annual approximation"
        ),
        "Worst Stress Return %": min((e["return_pct"] for e in events), default=np.nan),
        "Mean Stress Return %": mean("return_pct"),
        "Stress Market Excess %": mean("market_excess_pct"),
        "Stress Sector Excess %": mean("sector_excess_pct"),
        "Stress Drawdown %": mean("drawdown_pct"),
        "Stress Negative Months": mean("negative_months"),
        "Stress Downside Volatility %": mean("downside_volatility_pct"),
        "Post Trough 6M Return %": mean("post_trough_6m_pct"),
        "Post Trough 12M Return %": mean("post_trough_12m_pct"),
    }


def path_metrics(returns):
    values = np.asarray(returns, float)
    wealth = np.r_[1.0, np.cumprod(1 + values)]
    peak = np.maximum.accumulate(wealth)
    dd = wealth / peak - 1
    trough = int(np.argmin(dd))
    old_peak = int(np.argmax(wealth[: trough + 1]))
    recovery = np.flatnonzero(wealth[trough:] >= wealth[old_peak])
    return float(dd.min() * 100), (
        int(trough + recovery[0] - old_peak) if len(recovery) else None
    )


def select_top12(frame, score, previous=None, threshold=1.0):
    """Greedy cap with deterministic tie breaks and bounded incumbent preference."""
    table = frame.copy()
    incumbents = (
        set(previous["Symbol"])
        if isinstance(previous, pd.DataFrame) and not previous.empty
        else set()
    )
    table["Selection Priority"] = table[score] + table.Symbol.isin(incumbents) * max(
        0.0, threshold
    )
    ordered = table.sort_values(
        ["Selection Priority", score, "Symbol"], ascending=[False, False, True]
    )
    counts, selected = {}, []
    for idx, row in ordered.iterrows():
        if counts.get(row.Sector, 0) >= 4:
            continue
        selected.append(idx)
        counts[row.Sector] = counts.get(row.Sector, 0) + 1
        if len(selected) == 12:
            break
    if len(selected) != 12:
        raise ValueError(
            "Insufficient eligible sector diversity to select 12 stocks with a maximum of four per sector."
        )
    result = (
        table.loc[selected]
        .sort_values([score, "Symbol"], ascending=[False, True])
        .drop(columns="Selection Priority")
    )
    result.insert(0, "Rank", range(1, 13))
    return result.reset_index(drop=True)


def score_universe(
    market, years, monthly=None, live=None, simulations=5000, seed=42, horizon=5
):
    # No shortlist: every eligible stock enters the same model evaluation.
    market = market.copy()
    market["Sector"] = market["Sector"].replace(SECTOR_ALIASES)
    frame = screen_favorite_candidates(
        market, years, shortlist_per_sector=max(1, len(market))
    ).reset_index(drop=True)
    if len(frame) < 12:
        raise ValueError(
            "At least 12 stocks with valid sectors and three completed annual observations are required."
        )
    symbols = sorted(frame.Symbol.tolist())
    model = prepare_projection_model(market, symbols, years)
    state = build_current_market_state(symbols, live or {})
    validation = walk_forward_validate(
        model, np.ones(len(symbols)) / len(symbols), seed=seed
    )
    conditioned = condition_model_assumptions(
        model,
        state,
        "AUTO",
        {
            "starting_investment": 100000.0,
            "withdrawal_frequency": "No Withdrawal",
            "future_years": horizon,
        },
    )
    weights = validation.get("ensemble_weights") or {"Adaptive Regime Monte Carlo": 1.0}
    projected = project_candidates(
        model, conditioned, weights, horizon, simulations, seed
    )
    bear = deepcopy(conditioned)
    bear["initial_regime_probabilities"] = np.array([1.0, 0.0, 0.0])
    # Bear stress must actually use the regime model, not an unconditioned bootstrap.
    stressed = project_candidates(
        model, bear, {"Adaptive Regime Monte Carlo": 1.0}, horizon, simulations, seed
    )
    frame = frame.merge(projected, on="Symbol").merge(
        stressed.rename(columns={c: "Bear " + c for c in stressed if c != "Symbol"}),
        on="Symbol",
    )
    monthly_maps = _monthly_maps(monthly)
    histories = {
        s: pd.Series(v, dtype=float).sort_index() for s, v in monthly_maps.items()
    }
    histories = {s: h[(h > -1) & np.isfinite(h)] for s, h in histories.items()}
    market_history = histories.get("SPY", pd.Series(dtype=float))
    rows = []
    for _, row in frame.iterrows():
        annual = pd.to_numeric(row[years], errors="coerce").dropna().sort_index() / 100
        annual = annual[(annual > -1) & np.isfinite(annual)]
        hist = histories.get(row.Symbol, pd.Series(dtype=float))
        dd, recovery = path_metrics(hist if len(hist) >= 24 else annual)
        peers = [
            histories[s]
            for s in frame.loc[frame.Sector.eq(row.Sector), "Symbol"]
            if s != row.Symbol and s in histories
        ]
        info = {
            "Maximum Drawdown %": dd,
            "Recovery Periods": recovery,
            "Recovery Basis": "Monthly" if len(hist) >= 24 else "Annual",
            "Observed Months": len(hist),
            "Positive Months %": (
                float((hist > 0).mean() * 100) if len(hist) else np.nan
            ),
        }
        info.update(stress_evidence(hist, annual, market_history, peers))
        for n in (1, 2, 3, 5, 10, 15, 20):
            expected = [
                str(y) for y in range(int(max(years)) - n + 1, int(max(years)) + 1)
            ]
            info[f"{n}Y CAGR %"] = (
                _geometric_return(annual.loc[expected]) * 100
                if all(y in annual.index for y in expected)
                else np.nan
            )
        rows.append(info)
    frame = pd.concat([frame, pd.DataFrame(rows)], axis=1)
    rank = lambda c, high=True: _percentile_rank(frame[c], high)
    frame["Defense Score"] = pd.concat(
        [
            rank("Mean Stress Return %"),
            _percentile_rank(frame["Stress Market Excess %"]).where(
                frame["Stress Market Excess %"].notna()
            ),
            _percentile_rank(frame["Stress Sector Excess %"]).where(
                frame["Stress Sector Excess %"].notna()
            ),
        ],
        axis=1,
    ).mean(axis=1)
    frame["Drawdown Score"] = 0.6 * rank("Maximum Drawdown %") + 0.4 * rank(
        "Historical Volatility %", False
    )
    frame["Recovery Years"] = frame["Recovery Periods"] / np.where(
        frame["Recovery Basis"].eq("Monthly"), 12.0, 1.0
    )
    recovery_max = frame["Recovery Years"].max()
    recovery = frame["Recovery Years"].fillna(
        (float(recovery_max) if pd.notna(recovery_max) else 0) + 1000
    )
    frame["Recovery Score"] = _percentile_rank(recovery, False)
    frame["Bear Model Score"] = 0.55 * rank("Bear P10 Future Return %") + 0.45 * rank(
        "Bear P25 Future Return %"
    )
    frame["Consistency Score"] = rank("Positive Years %")
    frame["Profitability Score"] = rank("Historical CAGR %")
    # Extreme recent performance shrinks to longer history before normalization.
    long = frame["10Y CAGR %"].fillna(frame["Historical CAGR %"])
    core = frame["5Y CAGR %"].fillna(frame["Historical CAGR %"])
    recent = 0.5 * frame["3Y CAGR %"].fillna(core) + 0.5 * long
    frame["Historical Performance Score"] = _percentile_rank(
        0.20 * recent + 0.35 * core + 0.45 * long
    )
    frame["Recent Performance Score"] = _percentile_rank(recent)
    frame["Future P50 Score"] = rank("P50 Future Return %")
    frame["Future P75 Score"] = rank("P75 Future Return %")
    adjustments = state.get("holding_adjustments") or {}
    frame["Fundamentals Score"] = [
        float((adjustments.get(s) or {}).get("fundamental_score", 50))
        for s in frame.Symbol
    ]
    frame["Relative Strength Score"] = rank("6M")
    frame["Current Strength Score"] = (
        frame["Fundamentals Score"] + frame["Relative Strength Score"]
    ) / 2
    frame["Downside Quality Score"] = (
        rank("P10 Future Return %")
        + rank("P25 Future Return %")
        + rank("Maximum Drawdown %")
    ) / 3
    frame["Data Quality Score"] = [
        min(
            100,
            40
            + min(float(y), 10) * 3
            + (20 if m >= 60 else 0)
            + (10 if (adjustments.get(s) or {}).get("data_quality") == "High" else 0),
        )
        for s, y, m in zip(
            frame.Symbol, frame["Observed Years"], frame["Observed Months"]
        )
    ]
    frame["Data Confidence"] = pd.cut(
        frame["Data Quality Score"], [-1, 59, 84, 101], labels=["Low", "Medium", "High"]
    ).astype(str)
    frame["Risk Penalty"] = (
        np.maximum(0, frame["Historical Volatility %"] - 60) * 0.1
        + np.maximum(0, -frame["Maximum Drawdown %"] - 60) * 0.1
        + np.maximum(0, -frame["P25 Future Return %"]) * 0.1
    ).clip(0, 20)
    for kind, components in WEIGHTS.items():
        for name, weight in components.items():
            frame[kind + " Contribution: " + name] = frame[name + " Score"] * weight
        frame[kind + " Score"] = (
            sum(frame[name + " Score"] * weight for name, weight in components.items())
            - frame["Risk Penalty"]
        ).clip(0, 100)
    frame["Recession Additional Penalty"] = (
        np.maximum(0, -frame["Bear P25 Future Return %"]) * 0.15
        + frame["Recovery Periods"].isna() * 3
        + frame["Stress Events"].eq(0) * 5
    ).clip(0, 15)
    frame["Recession Score"] = (
        frame["Recession Score"] - frame["Recession Additional Penalty"]
    ).clip(0, 100)
    return frame, state, validation


def build_top12_rankings(
    market,
    years,
    monthly=None,
    live=None,
    simulations=5000,
    seed=42,
    previous=None,
    threshold=1.0,
):
    completed = [
        str(y)
        for y in years
        if str(y).isdigit()
        and int(y) < datetime.now(timezone.utc).year
        and str(y) in market
    ]
    frame, state, validation = score_universe(
        market, completed, monthly, live, simulations, seed
    )
    output = {}
    for kind in WEIGHTS:
        selected = select_top12(
            frame, kind + " Score", (previous or {}).get(kind), threshold
        )
        selected["Why Selected"] = [
            (
                f"Defense {r['Defense Score']:.1f}/100; drawdown {r['Maximum Drawdown %']:.1f}%; {int(r['Stress Events'])} stress windows ({r['Stress Evidence Basis']}); Bear P25 {r['Bear P25 Future Return %']:.1f}%."
                if kind == "Recession"
                else f"Historical performance {r['Historical Performance Score']:.1f}/100; P50/P75 annualized {r['P50 Future Return %']:.1f}%/{r['P75 Future Return %']:.1f}%; downside quality {r['Downside Quality Score']:.1f}/100."
            )
            for _, r in selected.iterrows()
        ]
        output[kind] = selected
    output.update(
        all_scores=frame,
        market_state=state,
        validation=validation,
        metadata={
            "Ranking Generated": datetime.now(timezone.utc).isoformat(),
            "Universe Evaluated": len(market),
            "Eligible Stocks": len(frame),
            "Excluded Stocks": len(market[market.Type.eq("Stock")]) - len(frame),
            "Historical Through": max(completed),
            "Model Version": "5.11.6",
            "Seed": seed,
            "Simulations": simulations,
            "Replacement Threshold": threshold,
        },
    )
    output["warnings"] = [
        "Monthly stress metrics are unavailable for securities without complete monthly windows; annual approximations are explicitly labeled.",
        "The absence of historical universe membership and sector snapshots prevents certified point-in-time validation.",
    ]
    output["metadata"]["Data Mode"] = (
        "Recent supplemental context plus historical data"
        if state.get("live_conditioning_active")
        else "Historical snapshot fallback; supplemental context unavailable"
    )
    return output


def walk_forward_rankings(market, years, seed=42):
    """Re-run actual scoring with truncated evidence. Never use current live inputs.

    Current-universe/sector survivorship remains a disclosed data limitation.
    """
    years = sorted(
        [str(y) for y in years if str(y).isdigit() and str(y) in market], key=int
    )
    records = []
    for cutoff in (2010, 2012, 2014, 2016, 2018, 2020, 2022, 2024):
        known = [y for y in years if int(y) <= cutoff]
        if len(known) < 3:
            continue
        # Strip all current quote, trend, valuation and fundamental columns.
        past = market[
            [c for c in ["Symbol", "Name", "Type", "Sector", *known] if c in market]
        ].copy()
        try:
            frame, _, _ = score_universe(past, known, simulations=300, seed=seed)
        except ValueError:
            continue
        for kind in WEIGHTS:
            try:
                picks = select_top12(frame, kind + " Score", threshold=0)
            except ValueError:
                continue
            for horizon in (1, 3, 5):
                future = [str(y) for y in range(cutoff + 1, cutoff + horizon + 1)]
                if not all(y in years for y in future):
                    continue
                actual = (
                    market.set_index("Symbol")[future].apply(
                        pd.to_numeric, errors="coerce"
                    )
                    / 100
                )
                selected = actual.reindex(picks.Symbol)
                # Do not discard failed/missing holdings and redistribute their weight.
                if selected.isna().any().any():
                    continue
                annual = selected.mean(axis=0)
                total = float(np.prod(1 + annual) - 1) * 100
                universe = (
                    actual.reindex(frame.Symbol)
                    .dropna()
                    .apply(lambda r: np.prod(1 + r) - 1, axis=1)
                )
                spy = actual.loc["SPY"] if "SPY" in actual.index else None
                benchmark = (
                    float((np.prod(1 + spy) - 1) * 100)
                    if spy is not None and spy.notna().all()
                    else np.nan
                )
                sector_returns = []
                for _, p in picks.iterrows():
                    peers = market.loc[
                        market.Sector.eq(p.Sector) & market.Type.eq("Stock"), "Symbol"
                    ]
                    sector_returns.append(
                        actual.reindex(peers)
                        .dropna()
                        .apply(lambda r: np.prod(1 + r) - 1, axis=1)
                        .median()
                        * 100
                    )
                dd, recovery = path_metrics(annual)
                observation = {
                    "Ranking": kind,
                    "As Of": cutoff,
                    "Training Through": max(known),
                    "Evaluation Start": cutoff + 1,
                    "Horizon": horizon,
                    "Return %": total,
                    "CAGR %": ((1 + total / 100) ** (1 / horizon) - 1) * 100,
                    "Universe Median %": float(universe.median() * 100),
                    "S&P 500 %": benchmark,
                    "Sector Benchmark %": float(np.mean(sector_returns)),
                    "Maximum Drawdown %": dd,
                    "Worst Year %": float(annual.min() * 100),
                    "Recovery Years": recovery,
                }
                if spy is not None and spy.notna().all():
                    declining = spy < 0
                    observation["Downside Capture %"] = (
                        float(annual[declining].mean() / spy[declining].mean() * 100)
                        if declining.any()
                        else np.nan
                    )
                if horizon == 5:
                    observed_cagr = ((1 + selected).prod(axis=1) ** (1 / 5) - 1) * 100
                    assumptions = picks.set_index("Symbol").reindex(observed_cagr.index)
                    observation["Stock P10-P90 Coverage %"] = float(
                        (
                            (observed_cagr >= assumptions["P10 Future Return %"])
                            & (observed_cagr <= assumptions["P90 Future Return %"])
                        ).mean()
                        * 100
                    )
                    observation["Stock P25-P75 Coverage %"] = float(
                        (
                            (observed_cagr >= assumptions["P25 Future Return %"])
                            & (observed_cagr <= assumptions["P75 Future Return %"])
                        ).mean()
                        * 100
                    )
                    observation["Stock P50 Absolute CAGR Error pp"] = float(
                        (observed_cagr - assumptions["P50 Future Return %"])
                        .abs()
                        .median()
                    )
                records.append(observation)
    return pd.DataFrame(records)
