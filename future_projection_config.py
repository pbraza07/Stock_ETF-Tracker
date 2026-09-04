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


LIVE_ADAPTIVE_CONFIG = {
    "percentiles": [10, 25, 50, 75, 90],
    "regime_score_weights": {
        "economic": 0.20,
        "trend_breadth": 0.20,
        "volatility": 0.15,
        "credit_rates": 0.15,
        "earnings": 0.15,
        "valuation": 0.10,
        "momentum": 0.05,
    },
    "expected_return_weight_ranges": {
        "long_term_anchor": [0.40, 0.60],
        "security_history": [0.10, 0.20],
        "sector_category": [0.05, 0.15],
        "valuation_fundamentals": [0.10, 0.20],
        "live_macro_regime_momentum": [0.10, 0.20],
    },
    "expected_return_live_adjustment_bounds": [-0.035, 0.035],
    "analyst_adjustment_bounds": [-0.005, 0.005],
    "valuation_adjustment_bounds": [-0.015, 0.015],
    "fundamental_adjustment_bounds": [-0.015, 0.015],
    "momentum_adjustment_bounds": [-0.010, 0.010],
    "volatility_multiplier_bounds": [0.75, 1.80],
    "bear_correlation_stress": 0.22,
    "normal_correlation_stress": 0.03,
    "bull_correlation_stress": 0.06,
    "bootstrap_block_months": 6,
    "bootstrap_block_years": 2,
    "ensemble_primary_floor": 0.50,
    "breadth_universe_limit": 75,
    "walk_forward_as_of_years": [2010, 2012, 2014, 2016, 2018, 2020, 2022, 2024],
    "walk_forward_horizons": [1, 3, 5],
    "stale_after_hours": {
        "market_prices": 36,
        "fundamentals": 24 * 14,
        "macro": 24 * 45,
        "volatility": 36,
        "analyst_estimates": 24 * 14,
        "historical_monthly": 24 * 45,
    },
}


LIVE_DATA_SOURCES = {
    "market_prices": {
        "source": "Yahoo Finance via yfinance",
        "use": "Prices, adjusted history, returns, volume, realized volatility, trend, beta, and market capitalization.",
    },
    "fundamentals": {
        "source": "Yahoo Finance quote-summary and analyst datasets via yfinance",
        "use": "Valuation, growth, profitability, leverage, cash flow, and bounded analyst-revision signals.",
    },
    "macro": {
        "source": "Federal Reserve Bank of St. Louis FRED (official-source series aggregation)",
        "use": "Rates, yield curves, inflation, labor, GDP, recession, and credit-spread conditioning.",
    },
    "volatility": {
        "source": "Yahoo Finance CBOE Volatility Index history and adjusted market history",
        "use": "VIX environment plus 20-day, 60-day, and 1-year realized volatility.",
    },
}


FRED_SERIES = {
    "federal_funds_rate": "FEDFUNDS",
    "treasury_2y": "DGS2",
    "treasury_10y": "DGS10",
    "yield_spread_10y_2y": "T10Y2Y",
    "yield_spread_10y_3m": "T10Y3M",
    "cpi": "CPIAUCSL",
    "unemployment_rate": "UNRATE",
    "payrolls": "PAYEMS",
    "real_gdp": "GDPC1",
    "credit_spread": "BAA10Y",
    "recession_indicator": "SAHMREALTIME",
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


def live_adaptive_config() -> dict:
    """Return the governed live-conditioning and calibration configuration."""

    return deepcopy(LIVE_ADAPTIVE_CONFIG)


def live_data_sources() -> dict:
    """Return auditable source descriptions for every supplemental data family."""

    return deepcopy(LIVE_DATA_SOURCES)


def fred_series() -> dict:
    """Return the official macro series identifiers used by the live loader."""

    return deepcopy(FRED_SERIES)
