"""Governed assumptions for MarketScope's Future Projection model.

Assumptions live here deliberately: the Monte Carlo engine imports this module
instead of hiding capital-market or regime constants inside calculation code.
Values are decimal returns/rates unless a label explicitly says otherwise.
"""

from __future__ import annotations

from copy import deepcopy


CAPITAL_MARKET_ASSUMPTIONS = {
    "broad_market_annual_geometric_return": {
        "value": 0.07,
        "source": "MarketScope model-governance baseline (not a third-party forecast)",
        "as_of_date": "2026-01-01",
        "last_updated_date": "2026-09-03",
        "description": (
            "Long-run nominal broad-market anchor used only as a shrinkage target; "
            "security and category evidence can move the final expected return."
        ),
    },
}


MODEL_DEFAULTS = {
    "simulation_counts": {
        "Standard": 5_000,
        "Advanced": 20_000,
        "High Precision": 50_000,
    },
    "default_quality": "Advanced",
    "student_t_degrees_of_freedom": 6,
    "stock_specific_excess_return_weight": 0.20,
    "sector_category_excess_return_weight": 0.10,
    "capital_market_anchor_weight": 0.70,
    "residual_covariance_shrinkage": 0.55,
    "expected_annual_geometric_return_floor": 0.01,
    "expected_annual_geometric_return_ceiling": 0.16,
    "individual_annual_return_floor": -0.95,
    "individual_annual_return_ceiling": 2.00,
    "individual_monthly_return_floor": -0.75,
    "individual_monthly_return_ceiling": 1.50,
    "minimum_credible_annual_periods": 3,
    "minimum_high_confidence_annual_periods": 10,
    "minimum_high_confidence_monthly_periods": 60,
    "regime_order": ["Bear", "Normal", "Bull"],
    "initial_regime_probabilities": [0.18, 0.62, 0.20],
    "regime_transition_matrix": [
        [0.58, 0.37, 0.05],
        [0.10, 0.78, 0.12],
        [0.05, 0.38, 0.57],
    ],
    "regime_annual_log_return_adjustments": {
        "Bear": -0.16,
        "Normal": 0.00,
        "Bull": 0.10,
    },
    "regime_volatility_multipliers": {
        "Bear": 1.45,
        "Normal": 0.85,
        "Bull": 1.00,
    },
}


MODEL_LIMITATIONS = [
    "Projections are hypothetical distributions, not guaranteed outcomes.",
    "Historical returns, correlations, and regimes may not repeat in the future.",
    "Taxes, trading spreads, and security-specific corporate events are not modeled.",
    "Imputed history lowers confidence and is always identified in diagnostics.",
    "Extreme outcomes outside configured return bounds are clipped for numerical stability.",
]


def capital_market_assumptions() -> dict:
    """Return a defensive copy suitable for display and export."""

    return deepcopy(CAPITAL_MARKET_ASSUMPTIONS)


def model_defaults() -> dict:
    """Return a defensive copy so callers cannot mutate global governance values."""

    return deepcopy(MODEL_DEFAULTS)

