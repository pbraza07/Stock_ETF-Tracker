from __future__ import annotations

from pathlib import Path
import re

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from future_projection import (
    prepare_projection_model,
    projection_payload_from_simulator,
    run_future_projection,
    validate_projection_inputs,
)
from future_projection_live import (
    block_bootstrap_indices,
    build_current_market_state,
    condition_model_assumptions,
    fetch_live_projection_context,
    walk_forward_validate,
)


ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "future_projection_ui.py").read_text(encoding="utf-8")
CSS = (ROOT / "styles.css").read_text(encoding="utf-8")
YEARS = [str(year) for year in range(2025, 2007, -1)]
SYMBOLS = ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]


def market_fixture() -> pd.DataFrame:
    rows = []
    for index, symbol in enumerate(SYMBOLS):
        row = {
            "Symbol": symbol,
            "Name": f"Company {symbol}",
            "Type": "ETF" if symbol == "CCC" else "Stock",
            "Sector": "Technology" if index % 2 == 0 else "Health Care",
            "MarketCap": 900_000_000_000 - index * 50_000_000_000,
        }
        for year in YEARS:
            row[year] = float(np.random.default_rng(index * 100 + int(year)).normal(8.0, 15.0))
        rows.append(row)
    return pd.DataFrame(rows)


def history(seed: int, drift: float = 0.08, volatility: float = 0.20) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2025-01-02", periods=300, freq="B")
    close = 100.0 * np.exp(np.cumsum(rng.normal(drift / 252.0, volatility / np.sqrt(252.0), len(dates))))
    return pd.DataFrame({"Close": close, "Volume": np.full(len(dates), 1_000_000)}, index=dates)


def live_fixture() -> dict:
    histories = {symbol: history(index + 1, 0.07 + index * 0.005, 0.18 + index * 0.01) for index, symbol in enumerate(SYMBOLS)}
    histories.update({"SPY": history(30, 0.07, 0.16), "QQQ": history(31, 0.08, 0.22), "IWM": history(32, 0.06, 0.24), "^VIX": history(33, 0.0, 0.35)})
    fundamentals = {}
    for index, symbol in enumerate(SYMBOLS):
        fundamentals[symbol] = {
            "instrument_type": "ETF" if symbol == "CCC" else "Stock",
            "forward_pe": 18.0 + index,
            "revenue_growth": 0.08,
            "earnings_growth": 0.10,
            "operating_margin": 0.18,
            "free_cash_flow": 1_000_000_000,
            "debt_to_equity": 45.0,
            "return_on_equity": 0.20,
            "eps_revision_direction": 0.25,
            "market_cap": 900_000_000_000 - index * 50_000_000_000,
            "sector": "Technology" if index % 2 == 0 else "Health Care",
            "retrieved_at": "2026-09-04T12:00:00+00:00",
        }
    return {
        "retrieved_at": "2026-09-04T12:00:00+00:00",
        "history_through": "2026-02-25",
        "histories": histories,
        "prices": {symbol: 120.0 + index for index, symbol in enumerate(SYMBOLS)},
        "fundamentals": fundamentals,
        "macro": {
            "federal_funds_rate": {"value": 3.5, "observation_date": "2026-08-01"},
            "yield_spread_10y_2y": {"value": 0.5, "observation_date": "2026-09-03"},
            "yield_spread_10y_3m": {"value": 0.3, "observation_date": "2026-09-03"},
            "credit_spread": {"value": 1.5, "observation_date": "2026-09-03"},
            "cpi": {"observations": [{"value": 100 + i * 0.2} for i in range(14)], "observation_date": "2026-08-01"},
            "unemployment_rate": {"observations": [{"value": 4.0}] * 4, "observation_date": "2026-08-01"},
            "payrolls": {"observations": [{"value": 100.0}, {"value": 100.15}], "observation_date": "2026-08-01"},
            "real_gdp": {"observations": [{"value": 100 + i} for i in range(5)], "observation_date": "2026-06-30"},
        },
        "breadth_symbols": SYMBOLS,
        "failures": [],
    }


def inputs(holdings=None, **updates) -> dict:
    value = {
        "starting_investment": 300_000.0,
        "withdrawal_frequency": "Yearly",
        "annual_withdrawal": 20_000.0,
        "monthly_withdrawal": 2_000.0,
        "withdrawal_timing": "End of period",
        "future_years": 3,
        "forecast_start_year": 2028,
        "holdings": ["AAA"] if holdings is None else holdings,
        "allocation_mode": "Equal Split",
        "allocations": {},
        "strategy": "Both",
        "projection_profile": "AUTO",
        "rebalancing_frequency": "Yearly",
        "scenario_quality": "Standard",
        "simulation_count": 160,
        "random_seed": 9001,
        "include_no_withdrawal_comparison": True,
    }
    value.update(updates)
    return value


def test_unlimited_holdings_accepts_one_and_more_than_four():
    for holdings in (["AAA"], SYMBOLS):
        errors, _ = validate_projection_inputs(inputs(holdings), market_fixture())
        assert not errors
        result = run_future_projection(market_fixture(), inputs(holdings), YEARS)
        expected = 100.0 / len(holdings)
        assert all(np.isclose(weight, expected) for weight in result["inputs"]["allocations"].values())


def test_empty_portfolio_is_the_only_count_validation_error():
    errors, _ = validate_projection_inputs(inputs([]), market_fixture())
    assert any("at least one" in message for message in errors)
    assert "all four" not in " ".join(errors).lower()


def test_simulator_handoff_preserves_every_supplied_holding():
    payload = projection_payload_from_simulator({}, SYMBOLS)
    assert payload["holdings"] == SYMBOLS
    assert len(payload["allocations"]) == len(SYMBOLS)


def test_dynamic_start_year_controls_every_output_label():
    result = run_future_projection(market_fixture(), inputs(["AAA", "BBB"], forecast_start_year=2032), YEARS)
    assert result["metadata"]["forecast_start_year"] == 2032
    assert result["metadata"]["forecast_end_year"] == 2034
    assert result["strategies"]["Rebalanced"]["table"]["Year"].tolist() == [2032, 2033, 2034]


def test_only_governed_percentiles_are_calculated_and_ordered():
    result = run_future_projection(market_fixture(), inputs(SYMBOLS), YEARS, live_context=live_fixture())
    table = result["strategies"]["Rebalanced"]["table"]
    for metric in ("Ending Balance", "Profit", "Annual Return %"):
        values = table[[f"P{p} {metric}" for p in (10, 25, 50, 75, 90)]].to_numpy()
        assert np.all(np.diff(values, axis=1) >= -1e-8)
    column_text = " ".join(table.columns)
    assert not re.search(r"\bP5\b|\bP95\b", column_text)


def test_regime_probabilities_are_dynamic_and_sum_to_100():
    state = build_current_market_state(SYMBOLS, live_fixture())
    probabilities = state["regime_probabilities"]
    assert set(probabilities) == {"Bear", "Normal", "Bull"}
    assert np.isclose(sum(probabilities.values()), 100.0)
    assert state["live_conditioning_active"] is True


def test_historical_fallback_is_explicit_and_preserves_static_initial_state():
    state = build_current_market_state(["AAA"], {"failures": ["offline"]})
    assert state["live_conditioning_active"] is False
    assert state["projection_confidence"] == "Low"
    assert state["regime_probabilities"] == {"Bear": 18.0, "Normal": 62.0, "Bull": 20.0}


def test_expected_return_adjustments_are_bounded_and_valuation_mean_reverts():
    live = live_fixture()
    live["fundamentals"]["AAA"]["forward_pe"] = 80.0
    live["fundamentals"]["BBB"]["forward_pe"] = 8.0
    state = build_current_market_state(["AAA", "BBB"], live)
    expensive = state["holding_adjustments"]["AAA"]
    inexpensive = state["holding_adjustments"]["BBB"]
    assert expensive["valuation_adjustment"] < inexpensive["valuation_adjustment"]
    assert all(-0.035 <= item["total_expected_return_adjustment"] <= 0.035 for item in state["holding_adjustments"].values())


def test_fundamentals_affect_the_security_adjustment_without_price_forecast():
    live = live_fixture()
    live["fundamentals"]["AAA"].update({"earnings_growth": 0.30, "revenue_growth": 0.25, "free_cash_flow": 2e9})
    live["fundamentals"]["BBB"].update({"earnings_growth": -0.30, "revenue_growth": -0.20, "free_cash_flow": -2e9})
    state = build_current_market_state(["AAA", "BBB"], live)
    assert state["holding_adjustments"]["AAA"]["fundamental_score"] > state["holding_adjustments"]["BBB"]["fundamental_score"]
    assert "future_price" not in state["holding_adjustments"]["AAA"]


def test_dynamic_volatility_and_correlation_change_covariance():
    market = market_fixture()
    model = prepare_projection_model(market, ["AAA", "BBB", "CCC"], YEARS)
    state = build_current_market_state(["AAA", "BBB", "CCC"], live_fixture())
    conditioned = condition_model_assumptions(model, state, "AUTO", inputs(["AAA", "BBB", "CCC"]))
    assert conditioned["period_covariance"].shape == model.period_covariance.shape
    assert not np.allclose(conditioned["period_covariance"], model.period_covariance)
    assert conditioned["correlation_stress"] >= 0


def test_stress_test_increases_bear_persistence_and_does_not_raise_return():
    model = prepare_projection_model(market_fixture(), ["AAA", "BBB"], YEARS)
    state = build_current_market_state(["AAA", "BBB"], live_fixture())
    balanced = condition_model_assumptions(model, state, "BALANCED", inputs(["AAA", "BBB"]))
    stressed = condition_model_assumptions(model, state, "STRESS TEST", inputs(["AAA", "BBB"]))
    assert stressed["regime_transition_matrix"][0, 0] > balanced["regime_transition_matrix"][0, 0]
    assert np.all(stressed["expected_annual_returns"] <= balanced["expected_annual_returns"] + 1e-12)


def test_block_bootstrap_keeps_contiguous_multi_period_blocks():
    indices = block_bootstrap_indices(12, 8, 30, 3, np.random.default_rng(42))
    assert indices.shape == (12, 8)
    assert np.all(indices[1] == indices[0] + 1)
    assert np.all(indices[2] == indices[0] + 2)


def test_walk_forward_backtest_prevents_future_leakage_and_weights_primary_model():
    model = prepare_projection_model(market_fixture(), ["AAA", "BBB", "CCC"], YEARS)
    result = walk_forward_validate(model, np.asarray([0.4, 0.3, 0.3]), seed=22)
    assert result["no_future_leakage"] is True
    assert result["ensemble_weights"]["Adaptive Regime Monte Carlo"] >= 0.50
    assert np.isclose(sum(result["ensemble_weights"].values()), 1.0)


def test_fixed_seed_and_live_inputs_are_reproducible():
    kwargs = dict(market=market_fixture(), inputs=inputs(["AAA", "BBB", "CCC"]), annual_year_columns=YEARS, live_context=live_fixture())
    first = run_future_projection(**kwargs)
    second = run_future_projection(**kwargs)
    for strategy in first["strategies"]:
        assert_frame_equal(first["strategies"][strategy]["table"], second["strategies"][strategy]["table"])


def test_live_projection_audit_contains_required_reproducibility_fields():
    result = run_future_projection(market_fixture(), inputs(["AAA", "BBB"]), YEARS, live_context=live_fixture())
    audit = result["audit"]
    required = {"projection_timestamp", "prices_used", "data_as_of_dates", "current_regime_probabilities", "expected_return_assumptions", "volatility_multipliers", "correlation_matrix", "model_weights", "random_seed", "number_of_simulations", "selected_strategy", "warnings", "confidence_score", "data_sources"}
    assert required.issubset(audit)


def test_live_ingestion_combines_provider_families_without_silent_zeros(monkeypatch):
    live = live_fixture()

    class FakeProvider:
        def download_daily_history(self, symbols, period="1y"):
            return {symbol: live["histories"].get(symbol, history(90)) for symbol in symbols}

        def download_live_prices(self, symbols):
            return {symbol: 123.45 for symbol in symbols}

        def get_projection_fundamentals_many(self, symbols, max_workers=4):
            return {symbol: live["fundamentals"].get(symbol, {}) for symbol in symbols}

    monkeypatch.setattr("future_projection_live.fetch_macro_context", lambda: live["macro"])
    monkeypatch.setattr(pd, "to_pickle", lambda *args, **kwargs: None)
    context = fetch_live_projection_context(FakeProvider(), ["AAA", "BBB"], market_fixture())
    assert context["prices"]["AAA"] == 123.45
    assert context["fundamentals"]["AAA"]["forward_pe"] is not None
    assert context["macro"]["federal_funds_rate"]["value"] == 3.5


def test_quote_failure_uses_labeled_marketscope_snapshot(monkeypatch):
    live = live_fixture()
    market = market_fixture()
    market["Price"] = [101.0 + index for index in range(len(market))]
    market["Snapshot Updated ET"] = "2026-09-04T16:00:00+00:00"

    class SnapshotFallbackProvider:
        def download_daily_history(self, symbols, period="1y"):
            return {symbol: live["histories"].get(symbol, history(91)) for symbol in symbols}

        def download_live_prices(self, symbols):
            raise RuntimeError("quote feed unavailable")

        def get_projection_fundamentals_many(self, symbols, max_workers=4):
            return {}

    monkeypatch.setattr("future_projection_live.fetch_macro_context", lambda: {})
    monkeypatch.setattr(pd, "to_pickle", lambda *args, **kwargs: None)
    context = fetch_live_projection_context(SnapshotFallbackProvider(), ["AAA"], market)
    state = build_current_market_state(["AAA"], context)

    assert context["prices"]["AAA"] == 101.0
    assert context["price_status"] == "LATEST AVAILABLE"
    assert context["snapshot_as_of"] == "2026-09-04T16:00:00+00:00"
    assert state["data_freshness"]["Market prices"]["status"].endswith("LATEST AVAILABLE")
    assert state["data_freshness"]["Market prices"]["updated"] == "2026-09-04T16:00:00+00:00"


def test_withdrawal_depletion_and_rebalanced_non_rebalanced_paths_survive_upgrade():
    result = run_future_projection(
        market_fixture(),
        inputs(["AAA", "BBB", "CCC"], starting_investment=1_000.0, annual_withdrawal=1_000_000.0, future_years=2),
        YEARS,
        live_context=live_fixture(),
    )
    for payload in result["strategies"].values():
        assert payload["summary"]["Median Depletion Year"] == 2028
        assert (payload["table"]["P10 Ending Balance"] >= 0).all()


def test_ui_contract_has_single_unlimited_selector_dynamic_year_and_five_toggles():
    assert 'st.multiselect(\n            "Stocks & ETFs"' in UI
    assert "Projection Start Year" in UI
    assert "fp_forecast_start_year" in UI
    for percentile in (10, 25, 50, 75, 90):
        assert f'f"P{{percentile}}"' in UI or f'P{percentile}' in UI
    assert not re.search(r"\bP5\b|\bP95\b", UI)
    assert "Annual Profit" in UI and "Annual Return %" in UI and "Model Comparison" in UI


def test_responsive_cards_expand_and_mobile_layout_stacks():
    assert "repeat(auto-fit" in CSS
    assert "height: auto" in CSS
    assert "overflow-wrap: anywhere" in CSS
    assert ".fp-summary-grid { grid-template-columns: 1fr; }" in CSS
