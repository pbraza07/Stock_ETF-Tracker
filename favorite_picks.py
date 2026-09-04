"""Evidence-backed Favorite Picks ranking for MarketScope.

The ranking reuses Future Projection's historical shrinkage, live market-state
conditioning, Markov regimes, Student-t shocks, block bootstrap, and factor/CMA
cross-check.  It ranks stocks within their own sector and never changes the
historical simulator or presents a pick as a guaranteed outcome.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Iterable

import numpy as np
import pandas as pd

from future_projection import PreparedProjectionModel, prepare_projection_model
from future_projection_config import capital_market_assumptions, model_defaults
from future_projection_live import (
    _history_matrix,
    block_bootstrap_indices,
    build_current_market_state,
    condition_model_assumptions,
    walk_forward_validate,
)


PERCENTILES = (10, 25, 50, 75, 90)
DEFAULT_PROJECTION_YEARS = 5
DEFAULT_SIMULATIONS = 5_000
DEFAULT_SHORTLIST_PER_SECTOR = 8
EXCLUDED_SECTORS = {"", "N/A", "NA", "NONE", "NAN", "UNKNOWN", "UNCLASSIFIED"}


def _number(value, default: float = float("nan")) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return float(default)
    return parsed if np.isfinite(parsed) else float(default)


def _percentile_rank(values: pd.Series, higher_is_better: bool = True) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    if numeric.notna().sum() <= 1:
        return pd.Series(50.0, index=values.index, dtype=float)
    fill = numeric.median() if numeric.notna().any() else 0.0
    ranked = numeric.fillna(fill).rank(method="average", pct=True, ascending=higher_is_better)
    if not higher_is_better:
        ranked = numeric.fillna(fill).rank(method="average", pct=True, ascending=False)
    return ranked.astype(float) * 100.0


def _geometric_return(values: Iterable[float]) -> float:
    clean = np.asarray([float(value) for value in values if np.isfinite(value) and float(value) > -1.0])
    if not len(clean):
        return float("nan")
    return float(np.expm1(np.mean(np.log1p(clean))))


def _annual_columns(market: pd.DataFrame, annual_year_columns: Iterable[str]) -> list[str]:
    available = set(map(str, market.columns))
    return sorted(
        {str(year) for year in annual_year_columns if str(year).isdigit() and str(year) in available},
        key=int,
    )


def screen_favorite_candidates(
    market: pd.DataFrame,
    annual_year_columns: Iterable[str],
    shortlist_per_sector: int = DEFAULT_SHORTLIST_PER_SECTOR,
) -> pd.DataFrame:
    """Screen every eligible stock, then retain a broad finalist set per sector."""

    if market is None or market.empty or "Symbol" not in market.columns:
        return pd.DataFrame()
    years = _annual_columns(market, annual_year_columns)
    if not years:
        return pd.DataFrame()
    frame = market.copy()
    if "Type" not in frame.columns:
        frame["Type"] = "Stock"
    if "Sector" not in frame.columns:
        frame["Sector"] = "Unknown"
    frame["Symbol"] = frame["Symbol"].astype(str).str.strip().str.upper()
    frame["Sector"] = frame["Sector"].astype(str).str.strip()
    valid_sector = ~frame["Sector"].str.upper().isin(EXCLUDED_SECTORS)
    frame = frame.loc[
        frame["Type"].astype(str).str.strip().str.upper().eq("STOCK")
        & frame["Symbol"].ne("")
        & valid_sector
    ].drop_duplicates("Symbol", keep="last").copy()
    if frame.empty:
        return frame

    annual = frame[years].apply(pd.to_numeric, errors="coerce") / 100.0
    annual = annual.where((annual > -1.0) & np.isfinite(annual))
    frame["Observed Years"] = annual.notna().sum(axis=1).astype(int)
    frame = frame.loc[frame["Observed Years"].ge(model_defaults()["minimum_credible_annual_periods"])].copy()
    annual = annual.loc[frame.index]
    if frame.empty:
        return frame

    frame["Historical CAGR %"] = annual.apply(lambda row: _geometric_return(row.dropna().tolist()) * 100.0, axis=1)
    frame["Historical Volatility %"] = annual.std(axis=1, ddof=1).fillna(0.18) * 100.0
    frame["Positive Years %"] = annual.gt(0).sum(axis=1) / annual.notna().sum(axis=1).clip(lower=1) * 100.0
    frame["Worst Historical Year %"] = annual.min(axis=1) * 100.0
    frame["Best Historical Year %"] = annual.max(axis=1) * 100.0
    worst_labels = []
    for index, row in annual.iterrows():
        valid = row.dropna()
        worst_labels.append(str(valid.idxmin()) if len(valid) else "N/A")
    frame["Worst Historical Year"] = worst_labels
    for column in ("1M", "3M", "6M", "YTD", "Price", "MarketCap"):
        frame[column] = pd.to_numeric(frame.get(column), errors="coerce")

    rating_points = {
        "STRONG BUY": 100.0,
        "BUY": 80.0,
        "HOLD": 50.0,
        "SELL": 20.0,
        "STRONG SELL": 0.0,
        "NOT RATED": 45.0,
    }
    frame["Analyst Score"] = frame.get("Analyst Rating", pd.Series("Not Rated", index=frame.index)).astype(str).str.upper().map(rating_points).fillna(45.0)
    short_buy = frame.get("Short Buy", pd.Series(False, index=frame.index)).fillna(False).astype(bool)
    long_buy = frame.get("Long Buy", pd.Series(False, index=frame.index)).fillna(False).astype(bool)
    fundamental_buy = frame.get("Fundamental Buy", pd.Series(False, index=frame.index)).fillna(False).astype(bool)
    frame["Active Buy Signals"] = short_buy.astype(int) + long_buy.astype(int) + fundamental_buy.astype(int)
    frame["Market Cap Log"] = np.log1p(frame["MarketCap"].clip(lower=0))

    components = []
    for _, group in frame.groupby("Sector", sort=True):
        scored = group.copy()
        scored["Historical Return Rank"] = _percentile_rank(scored["Historical CAGR %"])
        scored["Consistency Rank"] = _percentile_rank(scored["Positive Years %"])
        scored["Stability Rank"] = _percentile_rank(scored["Historical Volatility %"], higher_is_better=False)
        scored["Momentum Rank"] = _percentile_rank(scored["6M"])
        scored["Analyst Rank"] = _percentile_rank(scored["Analyst Score"])
        scored["Size Rank"] = _percentile_rank(scored["Market Cap Log"])
        scored["Pre-Screen Score"] = (
            0.30 * scored["Historical Return Rank"]
            + 0.20 * scored["Consistency Rank"]
            + 0.15 * scored["Stability Rank"]
            + 0.15 * scored["Momentum Rank"]
            + 0.10 * scored["Analyst Rank"]
            + 0.10 * scored["Size Rank"]
        )
        components.append(
            scored.sort_values(
                ["Pre-Screen Score", "Observed Years", "Symbol"],
                ascending=[False, False, True],
            ).head(max(2, int(shortlist_per_sector)))
        )
    return pd.concat(components, ignore_index=False).sort_values(["Sector", "Pre-Screen Score"], ascending=[True, False])


def favorite_candidate_symbols(
    market: pd.DataFrame,
    annual_year_columns: Iterable[str],
    shortlist_per_sector: int = DEFAULT_SHORTLIST_PER_SECTOR,
) -> list[str]:
    finalists = screen_favorite_candidates(market, annual_year_columns, shortlist_per_sector)
    return finalists["Symbol"].astype(str).tolist() if not finalists.empty else []


def _positive_semidefinite(matrix: np.ndarray, minimum: float = 1e-10) -> np.ndarray:
    symmetric = (np.asarray(matrix, dtype=float) + np.asarray(matrix, dtype=float).T) / 2.0
    values, vectors = np.linalg.eigh(symmetric)
    return (vectors * np.maximum(values, minimum)) @ vectors.T


def _ensemble_percentiles(
    model: PreparedProjectionModel,
    conditioned: dict,
    ensemble_weights: dict,
    projection_years: int,
    simulations: int,
    random_seed: int,
) -> pd.DataFrame:
    """Project every finalist with the same governed three-model ensemble."""

    defaults = model_defaults()
    rng = np.random.default_rng(int(random_seed))
    years = max(1, int(projection_years))
    simulation_count = max(100, int(simulations))
    count = len(model.symbols)
    covariance = _positive_semidefinite(np.asarray(conditioned["annual_covariance"], dtype=float))
    chol = np.linalg.cholesky(covariance)
    factor_covariance = _positive_semidefinite(covariance * 0.70)
    factor_chol = np.linalg.cholesky(factor_covariance)
    df = float(defaults["student_t_degrees_of_freedom"])
    t_scale = math.sqrt((df - 2.0) / df)
    transition = np.asarray(conditioned["regime_transition_matrix"], dtype=float)
    cumulative_transition = np.cumsum(transition, axis=1)
    regime = rng.choice(3, size=simulation_count, p=np.asarray(conditioned["initial_regime_probabilities"], dtype=float))
    regime_names = defaults["regime_order"]
    regime_return = np.asarray([defaults["regime_annual_log_return_adjustments"][name] for name in regime_names])
    regime_volatility = np.asarray([defaults["regime_volatility_multipliers"][name] for name in regime_names])

    model_names = ["Adaptive Regime Monte Carlo", "Historical Block Bootstrap", "Factor/CMA Model"]
    probabilities = np.asarray([max(0.0, _number(ensemble_weights.get(name), 0.0)) for name in model_names], dtype=float)
    probabilities = probabilities / probabilities.sum() if probabilities.sum() else np.asarray([1.0, 0.0, 0.0])
    assignments = rng.choice(3, size=simulation_count, p=probabilities)
    history_matrix, _ = _history_matrix(model)
    bootstrap_rows = block_bootstrap_indices(years, simulation_count, len(history_matrix), 2, rng)
    anchor = float(capital_market_assumptions()["broad_market_annual_geometric_return"]["value"])
    factor_expected = 0.75 * anchor + 0.25 * np.asarray(conditioned["expected_annual_returns"], dtype=float)
    factor_log = np.log1p(factor_expected)
    ending_growth = np.ones((simulation_count, count), dtype=float)

    for year_index in range(years):
        if year_index:
            draw = rng.random(simulation_count)
            next_regime = regime.copy()
            for current in range(3):
                mask = regime == current
                next_regime[mask] = np.searchsorted(cumulative_transition[current], draw[mask], side="right")
            regime = next_regime
        shocks = rng.standard_t(df, size=(simulation_count, count)) * t_scale
        correlated = shocks @ chol.T
        returns = np.expm1(
            np.asarray(conditioned["period_log_returns"], dtype=float)[None, :]
            + regime_return[regime, None]
            + correlated * regime_volatility[regime, None]
        )
        bootstrap_mask = assignments == 1
        if bootstrap_mask.any() and len(history_matrix):
            returns[bootstrap_mask] = history_matrix[bootstrap_rows[year_index, bootstrap_mask]]
        factor_mask = assignments == 2
        if factor_mask.any():
            factor_shocks = rng.standard_t(df, size=(int(factor_mask.sum()), count)) * t_scale
            returns[factor_mask] = np.expm1(factor_log[None, :] + factor_shocks @ factor_chol.T)
        returns = np.clip(
            returns,
            defaults["individual_annual_return_floor"],
            defaults["individual_annual_return_ceiling"],
        )
        ending_growth *= np.maximum(0.0, 1.0 + returns)

    annualized = np.power(np.maximum(ending_growth, 0.0), 1.0 / years) - 1.0
    rows = []
    for index, symbol in enumerate(model.symbols):
        row = {"Symbol": symbol}
        values = annualized[:, index] * 100.0
        quantiles = np.percentile(values, PERCENTILES)
        for percentile, value in zip(PERCENTILES, quantiles):
            row[f"P{percentile} {years}Y CAGR %"] = float(value)
        rows.append(row)
    return pd.DataFrame(rows)


def _data_quality_score(label: str) -> float:
    return {"High": 100.0, "Medium": 65.0, "Low": 30.0}.get(str(label), 30.0)


def _confidence_label(observed_years: int, data_quality: str) -> str:
    quality = str(data_quality)
    if observed_years >= 10 and quality == "High":
        return "High"
    if observed_years >= 5 and quality in {"High", "Medium"}:
        return "Medium"
    return "Low"


def _selection_reason(row: pd.Series, projection_years: int) -> str:
    facts = [
        (row.get("Projection Downside Rank", 0), f"P10 {projection_years}Y CAGR {row.get(f'P10 {projection_years}Y CAGR %', 0):+.1f}%"),
        (row.get("Projection Central Rank", 0), f"P50 {projection_years}Y CAGR {row.get(f'P50 {projection_years}Y CAGR %', 0):+.1f}%"),
        (row.get("Fundamental Score", 0), f"fundamentals {row.get('Fundamental Score', 0):.0f}/100"),
        (row.get("Valuation Score", 0), f"valuation {row.get('Valuation Score', 0):.0f}/100"),
        (row.get("Positive Years %", 0), f"positive in {row.get('Positive Years %', 0):.0f}% of observed years"),
        (row.get("Trend Score", 0), f"current trend score {row.get('Trend Score', 0):.0f}/100"),
    ]
    selected = [text for _, text in sorted(facts, key=lambda item: item[0], reverse=True)[:3]]
    return "; ".join(selected) + "."


def _key_risk(row: pd.Series, projection_years: int) -> str:
    risks = []
    if _number(row.get(f"P10 {projection_years}Y CAGR %"), 0.0) < 0:
        risks.append(f"downside model P10 is {row.get(f'P10 {projection_years}Y CAGR %'):+.1f}% CAGR")
    if _number(row.get("Conditioned Volatility %"), 0.0) >= 35.0:
        risks.append(f"elevated modeled volatility ({row.get('Conditioned Volatility %'):.1f}%)")
    if _number(row.get("Valuation Score"), 50.0) < 35.0:
        risks.append("valuation is expensive versus the model reference")
    if _number(row.get("Fundamental Score"), 50.0) < 40.0:
        risks.append("fundamental trend is below neutral")
    if int(_number(row.get("Observed Years"), 0)) < 10:
        risks.append(f"limited history ({int(_number(row.get('Observed Years'), 0))} completed years)")
    if str(row.get("Live Data Quality")) == "Low":
        risks.append("limited current-data coverage")
    return "; ".join(risks[:2]).capitalize() + "." if risks else "No single dominant flag; normal market and company-specific risk remains."


def build_favorite_picks(
    market: pd.DataFrame,
    annual_year_columns: Iterable[str],
    live_context: dict | None = None,
    projection_years: int = DEFAULT_PROJECTION_YEARS,
    simulations: int = DEFAULT_SIMULATIONS,
    random_seed: int = 20260904,
    shortlist_per_sector: int = DEFAULT_SHORTLIST_PER_SECTOR,
    data_as_of: str = "",
) -> dict:
    """Return the evidence table containing up to two selected stocks per sector."""

    years = _annual_columns(market, annual_year_columns)
    all_eligible = screen_favorite_candidates(market, years, shortlist_per_sector=10_000)
    finalists = screen_favorite_candidates(market, years, shortlist_per_sector=shortlist_per_sector)
    if finalists.empty:
        raise ValueError("No stocks have a valid sector and enough completed annual history to rank.")
    symbols = finalists["Symbol"].astype(str).tolist()
    model = prepare_projection_model(market, symbols, years)
    market_state = build_current_market_state(symbols, live_context)
    target = np.repeat(1.0 / len(symbols), len(symbols))
    validation = walk_forward_validate(model, target, seed=int(random_seed))
    conditioned = condition_model_assumptions(
        model,
        market_state,
        "AUTO",
        {
            "starting_investment": 100_000.0,
            "withdrawal_frequency": "No Withdrawal",
            "future_years": int(projection_years),
        },
    )
    ensemble_weights = validation.get("ensemble_weights") or {"Adaptive Regime Monte Carlo": 1.0}
    projected = _ensemble_percentiles(
        model,
        conditioned,
        ensemble_weights,
        projection_years,
        simulations,
        random_seed,
    )
    assumptions = model.holding_assumptions.rename(columns={"Ticker": "Symbol"}).copy()
    details = finalists.merge(assumptions, on="Symbol", how="left", suffixes=("", "_model")).merge(projected, on="Symbol", how="left")
    adjustments = market_state.get("holding_adjustments") or {}
    expected_by_symbol = dict(
        zip(model.symbols, np.asarray(conditioned["expected_annual_returns"], dtype=float) * 100.0)
    )
    volatility_by_symbol = dict(
        zip(
            model.symbols,
            np.sqrt(np.maximum(np.diag(conditioned["annual_covariance"]), 0.0)) * 100.0,
        )
    )
    details["Expected Annual Return %"] = details["Symbol"].map(expected_by_symbol)
    details["Conditioned Volatility %"] = details["Symbol"].map(volatility_by_symbol)

    def adjustment_value(symbol: str, key: str, default):
        return (adjustments.get(str(symbol)) or {}).get(key, default)

    details["Fundamental Score"] = details["Symbol"].map(
        lambda symbol: float(adjustment_value(symbol, "fundamental_score", 50.0))
    )
    details["Valuation Score"] = details["Symbol"].map(
        lambda symbol: float(adjustment_value(symbol, "valuation_score", 50.0))
    )
    details["Live Data Quality"] = details["Symbol"].map(
        lambda symbol: str(adjustment_value(symbol, "data_quality", "Low"))
    )
    details["Distance From 52W High %"] = details["Symbol"].map(
        lambda symbol: float(adjustment_value(symbol, "distance_from_52_week_high", float("nan"))) * 100.0
    )
    details["20D Return %"] = details["Symbol"].map(
        lambda symbol: float(adjustment_value(symbol, "return_20_day", float("nan"))) * 100.0
    )
    details["50D Return %"] = details["Symbol"].map(
        lambda symbol: float(adjustment_value(symbol, "return_50_day", float("nan"))) * 100.0
    )
    details["200D Return %"] = details["Symbol"].map(
        lambda symbol: float(adjustment_value(symbol, "return_200_day", float("nan"))) * 100.0
    )
    details["Trend Score"] = [
        float(np.clip(
            50.0
            + 15.0 * (1.0 if adjustment_value(symbol, "above_50_day_ma", False) else -1.0)
            + 15.0 * (1.0 if adjustment_value(symbol, "above_200_day_ma", False) else -1.0)
            + 50.0 * np.clip(_number(adjustment_value(symbol, "momentum_12_1", 0.0), 0.0), -0.4, 0.4),
            0.0,
            100.0,
        ))
        for symbol in details["Symbol"].astype(str)
    ]
    details["Data Quality Score"] = details["Live Data Quality"].map(_data_quality_score)
    details["History Depth Score"] = np.minimum(100.0, details["Observed Years"].astype(float) / 10.0 * 100.0)
    details["Risk-Adjusted Expected Return"] = details["Expected Annual Return %"] / details["Conditioned Volatility %"].replace(0, np.nan)

    scored_groups = []
    for _, group in details.groupby("Sector", sort=True):
        scored = group.copy()
        scored["Projection Downside Rank"] = _percentile_rank(scored[f"P10 {projection_years}Y CAGR %"])
        scored["Projection Conservative Rank"] = _percentile_rank(scored[f"P25 {projection_years}Y CAGR %"])
        scored["Projection Central Rank"] = _percentile_rank(scored[f"P50 {projection_years}Y CAGR %"])
        scored["Projection Strong Rank"] = _percentile_rank(scored[f"P75 {projection_years}Y CAGR %"])
        scored["Projection Upside Rank"] = _percentile_rank(scored[f"P90 {projection_years}Y CAGR %"])
        scored["Risk Adjusted Rank"] = _percentile_rank(scored["Risk-Adjusted Expected Return"])
        scored["Current Trend Rank"] = _percentile_rank(scored["Trend Score"])
        scored["Historical Evidence Rank"] = (
            0.55 * _percentile_rank(scored["Historical CAGR %"])
            + 0.25 * _percentile_rank(scored["Positive Years %"])
            + 0.20 * _percentile_rank(scored["Historical Volatility %"], higher_is_better=False)
        )
        scored["Favorite Score"] = (
            0.10 * scored["Projection Downside Rank"]
            + 0.10 * scored["Projection Conservative Rank"]
            + 0.10 * scored["Projection Central Rank"]
            + 0.03 * scored["Projection Strong Rank"]
            + 0.02 * scored["Projection Upside Rank"]
            + 0.12 * scored["Fundamental Score"]
            + 0.08 * scored["Valuation Score"]
            + 0.20 * scored["Historical Evidence Rank"]
            + 0.10 * scored["Current Trend Rank"]
            + 0.10 * scored["Risk Adjusted Rank"]
            + 0.025 * scored["Data Quality Score"]
            + 0.025 * scored["History Depth Score"]
        ).clip(0.0, 100.0)
        scored = scored.sort_values(
            ["Favorite Score", "Projection Conservative Rank", "Observed Years", "Symbol"],
            ascending=[False, False, False, True],
        )
        scored["Sector Rank"] = np.arange(1, len(scored) + 1)
        scored_groups.append(scored.head(2))
    picks = pd.concat(scored_groups, ignore_index=True).sort_values(["Sector", "Sector Rank"])
    picks["Model Confidence"] = [
        _confidence_label(int(years_observed), quality)
        for years_observed, quality in zip(picks["Observed Years"], picks["Live Data Quality"])
    ]
    picks["Why Selected"] = picks.apply(lambda row: _selection_reason(row, projection_years), axis=1)
    picks["Key Risk"] = picks.apply(lambda row: _key_risk(row, projection_years), axis=1)
    picks["Historical Worst Year"] = picks.apply(
        lambda row: f"{row.get('Worst Historical Year', 'N/A')} ({_number(row.get('Worst Historical Year %'), 0.0):+.2f}%)",
        axis=1,
    )
    picks["Data As Of"] = str(data_as_of or (live_context or {}).get("retrieved_at") or "Latest available")

    output_columns = [
        "Sector", "Sector Rank", "Symbol", "Name", "Favorite Score", "Model Confidence",
        "Current Price", "Analyst Rating", "Expected Annual Return %",
        *[f"P{percentile} {projection_years}Y CAGR %" for percentile in PERCENTILES],
        "Historical CAGR %", "Positive Years %", "Historical Worst Year",
        "Conditioned Volatility %", "6M", "Distance From 52W High %",
        "Fundamental Score", "Valuation Score", "Trend Score", "Observed Years",
        "Live Data Quality", "Why Selected", "Key Risk", "Data As Of",
    ]
    picks = picks.rename(columns={"Price": "Current Price"})
    for column in output_columns:
        if column not in picks.columns:
            picks[column] = np.nan
    warnings = list(model.warnings) + list(market_state.get("failures") or [])
    sector_counts = all_eligible.groupby("Sector")["Symbol"].nunique().to_dict() if not all_eligible.empty else {}
    for sector, count in sector_counts.items():
        if int(count) < 2:
            warnings.append(f"{sector} has only {int(count)} eligible stock, so fewer than two picks are shown.")
    return {
        "table": picks[output_columns].reset_index(drop=True),
        "eligible_stock_count": int(all_eligible["Symbol"].nunique()),
        "finalist_count": int(len(finalists)),
        "sector_count": int(picks["Sector"].nunique()),
        "pick_count": int(len(picks)),
        "projection_years": int(projection_years),
        "simulation_count": int(simulations),
        "random_seed": int(random_seed),
        "data_as_of": str(data_as_of or "Latest available"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "market_state": market_state,
        "ensemble_weights": ensemble_weights,
        "walk_forward_validation": validation,
        "warnings": list(dict.fromkeys(str(item) for item in warnings if str(item).strip())),
        "methodology": (
            "Every eligible stock is screened with completed annual history and the current MarketScope snapshot. "
            f"Up to {int(shortlist_per_sector)} finalists per sector receive live adaptive regime conditioning and a "
            "three-model ensemble. The final within-sector score gives 35% to projected percentiles, 20% to "
            "fundamentals/valuation, 20% to historical evidence, 10% to current trend, 10% to risk-adjusted expected "
            "return, and 5% to data quality/history depth. P10 and P25 receive more weight than P75 and P90."
        ),
    }
