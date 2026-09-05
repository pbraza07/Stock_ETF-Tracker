"""Batch single-stock projections; same governed assumptions as Favorite Picks."""

import math
import numpy as np
import pandas as pd
from favorite_picks import _number, _positive_semidefinite, PERCENTILES
from future_projection import PreparedProjectionModel
from future_projection_config import capital_market_assumptions, model_defaults
from future_projection_live import _history_matrix, block_bootstrap_indices


def project_candidates(
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
    covariance = _positive_semidefinite(
        np.asarray(conditioned["annual_covariance"], dtype=float)
    )
    chol = np.linalg.cholesky(covariance)
    factor_covariance = _positive_semidefinite(covariance * 0.70)
    factor_chol = np.linalg.cholesky(factor_covariance)
    df = float(defaults["student_t_degrees_of_freedom"])
    t_scale = math.sqrt((df - 2.0) / df)
    transition = np.asarray(conditioned["regime_transition_matrix"], dtype=float)
    cumulative_transition = np.cumsum(transition, axis=1)
    regime = rng.choice(
        3,
        size=simulation_count,
        p=np.asarray(conditioned["initial_regime_probabilities"], dtype=float),
    )
    regime_names = defaults["regime_order"]
    regime_return = np.asarray(
        [
            defaults["regime_annual_log_return_adjustments"][name]
            for name in regime_names
        ]
    )
    regime_volatility = np.asarray(
        [defaults["regime_volatility_multipliers"][name] for name in regime_names]
    )

    model_names = [
        "Adaptive Regime Monte Carlo",
        "Historical Block Bootstrap",
        "Factor/CMA Model",
    ]
    probabilities = np.asarray(
        [max(0.0, _number(ensemble_weights.get(name), 0.0)) for name in model_names],
        dtype=float,
    )
    probabilities = (
        probabilities / probabilities.sum()
        if probabilities.sum()
        else np.asarray([1.0, 0.0, 0.0])
    )
    assignments = rng.choice(3, size=simulation_count, p=probabilities)
    history_matrix, _ = _history_matrix(model)
    bootstrap_rows = block_bootstrap_indices(
        years, simulation_count, len(history_matrix), 2, rng
    )
    anchor = float(
        capital_market_assumptions()["broad_market_annual_geometric_return"]["value"]
    )
    factor_expected = 0.75 * anchor + 0.25 * np.asarray(
        conditioned["expected_annual_returns"], dtype=float
    )
    factor_log = np.log1p(factor_expected)
    ending_growth = np.ones((simulation_count, count), dtype=float)

    peak = ending_growth.copy()
    worst_drawdown = np.zeros_like(ending_growth)
    for year_index in range(years):
        if year_index:
            draw = rng.random(simulation_count)
            next_regime = regime.copy()
            for current in range(3):
                mask = regime == current
                next_regime[mask] = np.searchsorted(
                    cumulative_transition[current], draw[mask], side="right"
                )
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
            returns[bootstrap_mask] = history_matrix[
                bootstrap_rows[year_index, bootstrap_mask]
            ]
        factor_mask = assignments == 2
        if factor_mask.any():
            factor_shocks = (
                rng.standard_t(df, size=(int(factor_mask.sum()), count)) * t_scale
            )
            returns[factor_mask] = np.expm1(
                factor_log[None, :] + factor_shocks @ factor_chol.T
            )
        returns = np.clip(
            returns,
            defaults["individual_annual_return_floor"],
            defaults["individual_annual_return_ceiling"],
        )
        ending_growth *= np.maximum(0.0, 1.0 + returns)
        peak = np.maximum(peak, ending_growth)
        worst_drawdown = np.minimum(worst_drawdown, ending_growth / peak - 1.0)

    annualized = np.power(np.maximum(ending_growth, 0.0), 1.0 / years) - 1.0
    rows = []
    for index, symbol in enumerate(model.symbols):
        row = {"Symbol": symbol}
        values = annualized[:, index] * 100.0
        quantiles = np.percentile(values, PERCENTILES)
        for percentile, value in zip(PERCENTILES, quantiles):
            row[f"P{percentile} Future Return %"] = float(value)
            row[f"P{percentile} Projected Profit"] = float(
                np.percentile((ending_growth[:, index] - 1) * 100000, percentile)
            )
        row["Probability Positive %"] = float(
            np.mean(ending_growth[:, index] > 1) * 100
        )
        row["Probability Loss >20%"] = float(
            np.mean(ending_growth[:, index] < 0.8) * 100
        )
        row["Probability Loss >30%"] = float(
            np.mean(ending_growth[:, index] < 0.7) * 100
        )
        row["Expected Maximum Drawdown %"] = float(
            np.mean(worst_drawdown[:, index]) * 100
        )
        rows.append(row)
    return pd.DataFrame(rows)
