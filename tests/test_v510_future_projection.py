from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from future_projection import (
    _make_state,
    _step_state,
    prepare_projection_model,
    projection_payload_from_simulator,
    run_future_projection,
    validate_projection_inputs,
)


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
UI = (ROOT / "future_projection_ui.py").read_text(encoding="utf-8")
CSS = (ROOT / "styles.css").read_text(encoding="utf-8")
YEARS = ["2025", "2024", "2023", "2022", "2021", "2020"]


def market_fixture() -> pd.DataFrame:
    return pd.DataFrame([
        {"Symbol": "AAA", "Name": "Alpha", "Type": "Stock", "Sector": "Technology", "2025": 9, "2024": 14, "2023": 20, "2022": -15, "2021": 11, "2020": 25},
        {"Symbol": "BBB", "Name": "Beta", "Type": "Stock", "Sector": "Health Care", "2025": 6, "2024": 8, "2023": 5, "2022": 2, "2021": 12, "2020": 4},
        {"Symbol": "CCC", "Name": "Core ETF", "Type": "ETF", "Sector": "Broad Market", "Industry": "ETF / Fund", "2025": 8, "2024": 12, "2023": 17, "2022": -12, "2021": 10, "2020": 18},
        {"Symbol": "DDD", "Name": "Delta", "Type": "Stock", "Sector": "Energy", "2025": 4, "2024": 1, "2023": -3, "2022": 25, "2021": 6, "2020": -8},
        {"Symbol": "EEE", "Name": "Echo", "Type": "Stock", "Sector": "Technology", "2025": 10, "2024": 13, "2023": 16, "2022": -10, "2021": 9, "2020": 20},
    ])


def base_inputs(**updates) -> dict:
    value = {
        "starting_investment": 100_000.0,
        "withdrawal_frequency": "No Withdrawal",
        "annual_withdrawal": 10_000.0,
        "monthly_withdrawal": 1_000.0,
        "withdrawal_timing": "End of period",
        "future_years": 2,
        "holdings": ["AAA", "BBB", "CCC", "DDD"],
        "allocation_mode": "Equal Split",
        "allocations": {},
        "strategy": "Both",
        "rebalancing_frequency": "Yearly",
        "scenario_quality": "Standard",
        "simulation_count": 96,
        "random_seed": 1234,
        "include_no_withdrawal_comparison": True,
        "forecast_start_year": 2026,
    }
    value.update(updates)
    return value


def monthly_fixture(months: int = 24) -> dict:
    labels = pd.period_range("2024-01", periods=months, freq="M").astype(str).tolist()
    return {
        "returns": {
            symbol: {label: (0.004 + idx * 0.0002) for idx, label in enumerate(labels)}
            for symbol in ["AAA", "BBB", "CCC", "DDD"]
        }
    }


def test_01_four_stock_equal_allocation_without_withdrawal():
    result = run_future_projection(market_fixture(), base_inputs(), YEARS)
    assert result["inputs"]["allocations"] == {"AAA": 25.0, "BBB": 25.0, "CCC": 25.0, "DDD": 25.0}
    for payload in result["strategies"].values():
        assert (payload["table"]["Actual Withdrawal"] == 0).all()
        assert (payload["table"]["Median Ending Balance"] >= 0).all()


def test_02_yearly_withdrawal_is_processed_at_year_end():
    result = run_future_projection(
        market_fixture(),
        base_inputs(withdrawal_frequency="Yearly", annual_withdrawal=12_345.0, strategy="Rebalanced"),
        YEARS,
    )
    table = result["strategies"]["Rebalanced"]["table"]
    assert len(table) == 2
    assert np.allclose(table["Requested Withdrawal"], 12_345.0)
    assert (table["Actual Withdrawal"] <= table["Requested Withdrawal"] + 1e-8).all()


def test_03_monthly_withdrawal_is_processed_every_month():
    result = run_future_projection(
        market_fixture(),
        base_inputs(withdrawal_frequency="Monthly", monthly_withdrawal=700.0, future_years=1, strategy="Rebalanced"),
        YEARS,
        monthly_fixture(24),
    )
    table = result["strategies"]["Rebalanced"]["table"]
    assert len(table) == 12
    assert np.allclose(table["Requested Withdrawal"], 700.0)
    assert table.iloc[0]["Month"] == 1
    assert table.iloc[-1]["Month"] == 12


def test_04_beginning_of_period_withdrawal_precedes_return():
    target = np.full(4, 0.25)
    state = _make_state(1, 1_000.0, target)
    metrics = _step_state(
        state, np.full((1, 4), 0.10), 200.0, 0.0, 0.0,
        "Beginning of period", target, False, False, 0,
    )
    assert np.isclose(metrics["ending"][0], 880.0)
    assert np.isclose(metrics["gross"][0], 80.0)


def test_05_rebalanced_portfolio_returns_to_target_allocation():
    target = np.asarray([0.40, 0.30, 0.20, 0.10])
    state = _make_state(1, 1_000.0, target)
    _step_state(state, np.asarray([[1.0, 0.0, 0.0, 0.0]]), 0, 0, 0, "End of period", target, True, True, 0)
    assert np.allclose(state["holdings"][0] / state["holdings"][0].sum(), target)


def test_06_non_rebalanced_portfolio_retains_drifted_weights():
    target = np.full(4, 0.25)
    state = _make_state(1, 1_000.0, target)
    _step_state(state, np.asarray([[1.0, 0.0, 0.0, 0.0]]), 0, 0, 0, "End of period", target, False, False, 0)
    weights = state["holdings"][0] / state["holdings"][0].sum()
    assert weights[0] > 0.25
    assert not np.allclose(weights, target)


def test_07_non_rebalanced_withdrawal_is_pro_rata():
    target = np.asarray([0.40, 0.30, 0.20, 0.10])
    state = _make_state(1, 1_000.0, target)
    metrics = _step_state(state, np.zeros((1, 4)), 100.0, 0, 0, "End of period", target, False, False, 0)
    assert np.allclose(metrics["holding_withdrawal"][0], [40, 30, 20, 10])


def test_08_withdrawal_is_limited_to_available_value():
    target = np.full(4, 0.25)
    state = _make_state(1, 1_000.0, target)
    metrics = _step_state(state, np.zeros((1, 4)), 2_000.0, 0, 0, "End of period", target, False, False, 0)
    assert metrics["actual"][0] == 1_000.0
    assert metrics["shortfall"][0] == 1_000.0


def test_09_depleted_portfolio_never_becomes_negative_or_revives():
    target = np.full(4, 0.25)
    state = _make_state(1, 1_000.0, target)
    _step_state(state, np.zeros((1, 4)), 2_000.0, 500.0, 0, "End of period", target, False, False, 0)
    second = _step_state(state, np.ones((1, 4)), 100.0, 500.0, 0, "End of period", target, False, False, 1)
    assert second["ending"][0] == 0.0
    assert (state["holdings"] >= 0).all()


def test_10_exact_depletion_year_is_reported():
    result = run_future_projection(
        market_fixture(),
        base_inputs(starting_investment=1_000.0, withdrawal_frequency="Yearly", annual_withdrawal=1_000_000.0, future_years=3, strategy="Rebalanced"),
        YEARS,
    )
    assert result["strategies"]["Rebalanced"]["summary"]["Median Depletion Year"] == 2026


def test_11_exact_depletion_month_and_year_is_reported():
    result = run_future_projection(
        market_fixture(),
        base_inputs(starting_investment=1_000.0, withdrawal_frequency="Monthly", monthly_withdrawal=1_000_000.0, future_years=1, strategy="Rebalanced"),
        YEARS,
        monthly_fixture(24),
    )
    assert result["strategies"]["Rebalanced"]["summary"]["Median Depletion Month and Year"] == "2026-01"


def test_12_contributions_and_fees_follow_cash_flow_identity():
    target = np.full(4, 0.25)
    state = _make_state(1, 1_000.0, target)
    metrics = _step_state(state, np.zeros((1, 4)), 100.0, 50.0, 0.10, "End of period", target, False, False, 0)
    # 1000 + 0 - 100 + 50 - 95 = 855
    assert np.isclose(metrics["fees"][0], 95.0)
    assert np.isclose(metrics["ending"][0], 855.0)


def test_13_custom_allocations_must_total_exactly_100():
    valid = base_inputs(allocation_mode="Custom Allocation", allocations={"AAA": 40, "BBB": 30, "CCC": 20, "DDD": 10})
    invalid = base_inputs(allocation_mode="Custom Allocation", allocations={"AAA": 40, "BBB": 30, "CCC": 20, "DDD": 9.99})
    assert not validate_projection_inputs(valid, market_fixture())[0]
    assert any("exactly 100%" in message for message in validate_projection_inputs(invalid, market_fixture())[0])


def test_14_duplicate_ticker_validation():
    inputs = base_inputs(holdings=["AAA", "AAA", "CCC", "DDD"], allocation_mode="Custom Allocation", allocations={"AAA": 50, "CCC": 25, "DDD": 25})
    errors, _ = validate_projection_inputs(inputs, market_fixture())
    assert any("different ticker" in message for message in errors)


def test_14b_empty_holding_slots_are_validation_errors_not_keyerrors():
    empty_errors, _ = validate_projection_inputs(base_inputs(holdings=["", "", "", ""]), market_fixture())
    partial_errors, _ = validate_projection_inputs(base_inputs(holdings=["AAA", "BBB", "", ""]), market_fixture())
    assert any("Select all four" in message for message in empty_errors)
    assert any("Select all four" in message for message in partial_errors)
    assert not any("different ticker" in message for message in empty_errors + partial_errors)


def test_15_etf_can_be_mixed_with_stocks_and_keeps_fund_category():
    model = prepare_projection_model(market_fixture(), ["AAA", "BBB", "CCC", "DDD"], YEARS)
    etf = model.holding_assumptions.set_index("Ticker").loc["CCC"]
    assert etf["Type"] == "ETF"
    assert etf["Sector / ETF Category"] == "Broad Market"


def test_16_limited_history_is_imputed_and_lowers_confidence():
    market = market_fixture()
    market.loc[market["Symbol"].eq("AAA"), ["2024", "2023", "2022", "2021", "2020"]] = np.nan
    model = prepare_projection_model(market, ["AAA", "BBB", "CCC", "DDD"], YEARS)
    alpha = model.holding_assumptions.set_index("Ticker").loc["AAA"]
    assert alpha["Observed Annual Periods"] == 1
    assert alpha["Imputed Annual Periods"] == 5
    assert model.confidence == "Low"
    assert any("Limited-history blend" in warning for warning in model.warnings)
    market[YEARS] = market[YEARS].astype(float)
    market.loc[:, YEARS] = np.nan
    errors, _ = validate_projection_inputs(base_inputs(), market)
    assert any("too little completed historical data" in message for message in errors)


def test_17_same_inputs_and_seed_are_identical():
    first = run_future_projection(market_fixture(), base_inputs(), YEARS)
    second = run_future_projection(market_fixture(), base_inputs(), YEARS)
    for strategy in first["strategies"]:
        assert_frame_equal(first["strategies"][strategy]["table"], second["strategies"][strategy]["table"])
        assert first["strategies"][strategy]["summary"] == second["strategies"][strategy]["summary"]


def test_18_chart_values_are_the_exact_table_values():
    result = run_future_projection(market_fixture(), base_inputs(), YEARS)
    for payload in result["strategies"].values():
        assert_frame_equal(payload["table"], payload["chart"])
    assert result["diagnostics"]["chart_table_shared_source"] is True


def test_19_ranked_or_current_portfolio_loads_into_future_projection():
    payload = projection_payload_from_simulator({
        "portfolio_symbols": ["AAA", "BBB", "CCC", "DDD"],
        "portfolio_total_amount": 444_000,
        "portfolio_monthly_withdrawals_enabled": True,
        "portfolio_monthly_withdrawal": 5_500,
        "portfolio_annual_withdrawal": 66_000,
        "portfolio_allocation_mode": "Equal split",
    })
    assert payload["holdings"] == ["AAA", "BBB", "CCC", "DDD"]
    assert payload["starting_investment"] == 444_000
    assert payload["withdrawal_frequency"] == "Monthly"
    assert payload["monthly_withdrawal"] == 5_500
    assert payload["allocations"] == {"AAA": 25.0, "BBB": 25.0, "CCC": 25.0, "DDD": 25.0}
    assert "Project Future" in APP and "future_projection_pending_payload" in APP


def test_20_mobile_layout_stacks_cards_without_squeezed_numbers():
    assert "@media (max-width: 720px)" in CSS
    assert ".fp-summary-grid { grid-template-columns: 1fr; }" in CSS
    assert "overflow-wrap: anywhere" in CSS
    assert 'width="stretch"' in UI
    assert '"Future Projection"' in APP
