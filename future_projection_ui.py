"""Streamlit presentation layer for MarketScope Future Projection."""

from __future__ import annotations

import queue
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from html import escape
from typing import Callable

import numpy as np
import pandas as pd
import streamlit as st

from future_projection import (
    ProjectionValidationError,
    build_csv_export,
    build_excel_export,
    build_pdf_export,
    holding_category,
    parse_currency,
    projection_cache_key,
    run_future_projection,
    validate_projection_inputs,
)
from future_projection_config import capital_market_assumptions, model_defaults


DISCLAIMER = (
    "Future projections are probabilistic estimates based on historical data, current market conditions and model assumptions. "
    "Live data may improve model calibration but cannot predict future market returns or eliminate investment risk."
)
PERCENTILES = (10, 25, 50, 75, 90)
PERCENTILE_COLORS = {
    10: "#EF4444",
    25: "#F59E0B",
    50: "#2F80ED",
    75: "#14B8A6",
    90: "#A855F7",
}
PROFILE_HELP = {
    "AUTO": "Recommended. Adapts risk assumptions to the current regime, holdings, horizon, and withdrawal rate.",
    "Conservative": "Uses stronger return shrinkage and moderately higher volatility; emphasize P10 and P25.",
    "Balanced": "Uses the calibrated ensemble as-is; emphasize the P25-P75 planning range.",
    "Growth": "Uses the same probability engine without inflating returns; emphasizes P50 and P75 in interpretation.",
    "Stress Test": "Raises Bear-regime persistence, volatility, and correlations and includes severe downside behavior.",
}


def _money_text(value: float) -> str:
    return f"${float(value):,.2f}"


def _state_default(key: str, value) -> None:
    if key not in st.session_state:
        st.session_state[key] = value


def _initialize_state(latest_completed_year: int) -> None:
    first_forecast = int(latest_completed_year) + 1
    defaults = {
        "fp_starting_investment_text": "$400,000",
        "fp_withdrawal_frequency": "Yearly",
        "fp_annual_withdrawal_text": "$200,000",
        "fp_monthly_withdrawal_text": "$16,666.67",
        "fp_withdrawal_timing": "End of period",
        "fp_future_years": 10,
        "fp_forecast_start_year": first_forecast,
        "fp_holdings": [],
        "fp_allocation_mode": "Equal Split",
        "fp_maintenance_strategy": "Both",
        "fp_projection_profile": "AUTO",
        "fp_rebalancing_frequency": "Yearly",
        "fp_scenario_quality": "Advanced",
        "fp_inflation_adjust": False,
        "fp_withdrawal_inflation_pct": 2.5,
        "fp_management_fee_pct": 0.0,
        "fp_contribution_text": "$0",
        "fp_random_seed": 20260904,
        "fp_include_no_withdrawal": True,
        "fp_result": None,
        "fp_result_cache": {},
        "fp_running": False,
        "fp_chart_cumulative_withdrawals": False,
        "fp_chart_no_withdrawal": True,
        "fp_chart_measure": "Portfolio Balance",
        "fp_chart_probability_bands": True,
    }
    for percentile in PERCENTILES:
        defaults[f"fp_chart_p{percentile}"] = True
    cma_date = capital_market_assumptions()["broad_market_annual_geometric_return"]["as_of_date"]
    defaults["fp_cma_date"] = date.fromisoformat(cma_date)
    for key, value in defaults.items():
        _state_default(key, value)
    if int(st.session_state.fp_forecast_start_year) < first_forecast:
        st.session_state.fp_forecast_start_year = first_forecast


def _allocation_key(symbol: str) -> str:
    return "fp_allocation_" + "".join(ch if ch.isalnum() else "_" for ch in str(symbol).upper())


def _apply_payload(payload: dict) -> None:
    payload = dict(payload or {})
    holdings = list(dict.fromkeys(str(symbol).strip().upper() for symbol in payload.get("holdings") or [] if str(symbol).strip()))
    st.session_state.fp_starting_investment_text = _money_text(payload.get("starting_investment") or 400_000.0)
    st.session_state.fp_withdrawal_frequency = str(payload.get("withdrawal_frequency") or "No Withdrawal")
    st.session_state.fp_annual_withdrawal_text = _money_text(payload.get("annual_withdrawal") or 0.0)
    st.session_state.fp_monthly_withdrawal_text = _money_text(payload.get("monthly_withdrawal") or 0.0)
    st.session_state.fp_withdrawal_timing = str(payload.get("withdrawal_timing") or "End of period")
    st.session_state.fp_future_years = int(payload.get("future_years") or 10)
    st.session_state.fp_holdings = holdings
    st.session_state.fp_allocation_mode = str(payload.get("allocation_mode") or "Equal Split")
    st.session_state.fp_maintenance_strategy = str(payload.get("strategy") or "Both")
    st.session_state.fp_projection_profile = str(payload.get("projection_profile") or "AUTO")
    st.session_state.fp_rebalancing_frequency = str(payload.get("rebalancing_frequency") or "Yearly")
    allocations = dict(payload.get("allocations") or {})
    equal = 100.0 / len(holdings) if holdings else 0.0
    for symbol in holdings:
        st.session_state[_allocation_key(symbol)] = float(allocations.get(symbol, equal))
    st.session_state.fp_result = None


def _clear_portfolio() -> None:
    st.session_state.fp_holdings = []
    st.session_state.fp_result = None


def _reset_projection() -> None:
    for key in list(st.session_state.keys()):
        if str(key).startswith("fp_"):
            del st.session_state[key]


def _holding_option_label(symbol: str, lookup: pd.DataFrame) -> str:
    if symbol not in lookup.index:
        return symbol
    row = lookup.loc[symbol]
    if isinstance(row, pd.DataFrame):
        row = row.iloc[-1]
    return f"{symbol} - {row.get('Name') or symbol} | {row.get('Type') or 'Stock'} | {holding_category(row)}"


def _render_selected_holding_cards(
    holdings: list[str],
    lookup: pd.DataFrame,
    logo_loader: Callable[[tuple[str, ...]], dict] | None,
) -> None:
    selected = [symbol for symbol in holdings if symbol in lookup.index]
    if not selected:
        st.caption("No holdings selected. Use the searchable field above to add one or more stocks or ETFs.")
        return
    logos = {}
    if logo_loader is not None:
        try:
            logos = logo_loader(tuple(selected)) or {}
        except Exception:
            logos = {}
    cards = []
    for symbol in selected:
        row = lookup.loc[symbol]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[-1]
        name = str(row.get("Name") or symbol)
        instrument_type = str(row.get("Type") or "Stock")
        category = holding_category(row)
        logo = str(logos.get(symbol) or "")
        image = (
            f'<img src="{escape(logo, quote=True)}" alt="{escape(symbol)} logo">'
            if logo.startswith(("https://", "http://"))
            else f'<span class="fp-logo-fallback">{escape(symbol[:2])}</span>'
        )
        cards.append(
            '<div class="fp-holding-card">'
            f'{image}<div><b>{escape(symbol)}</b><span>{escape(name)}</span>'
            f'<small>{escape(instrument_type)} - {escape(category)}</small></div></div>'
        )
    st.markdown('<div class="fp-holding-grid">' + "".join(cards) + "</div>", unsafe_allow_html=True)


def _build_inputs() -> tuple[dict, list[str]]:
    parse_errors: list[str] = []
    parsed = {}
    for key, label, state_key in (
        ("starting", "Starting Investment", "fp_starting_investment_text"),
        ("annual", "Annual Withdrawal", "fp_annual_withdrawal_text"),
        ("monthly", "Monthly Withdrawal", "fp_monthly_withdrawal_text"),
        ("contribution", "Additional contribution", "fp_contribution_text"),
    ):
        try:
            parsed[key] = parse_currency(st.session_state.get(state_key))
        except ProjectionValidationError as exc:
            parsed[key] = -1.0 if key != "starting" else 0.0
            parse_errors.append(f"{label}: {exc}")
    holdings = list(dict.fromkeys(str(symbol).strip().upper() for symbol in st.session_state.fp_holdings if str(symbol).strip()))
    if st.session_state.fp_allocation_mode == "Equal Split":
        equal = 100.0 / len(holdings) if holdings else 0.0
        allocations = {symbol: equal for symbol in holdings}
    else:
        allocations = {symbol: float(st.session_state.get(_allocation_key(symbol), 0.0) or 0.0) for symbol in holdings}
    return {
        "starting_investment": parsed["starting"],
        "withdrawal_frequency": st.session_state.fp_withdrawal_frequency,
        "annual_withdrawal": parsed["annual"],
        "monthly_withdrawal": parsed["monthly"],
        "withdrawal_timing": st.session_state.fp_withdrawal_timing,
        "future_years": int(st.session_state.fp_future_years),
        "holdings": holdings,
        "allocation_mode": st.session_state.fp_allocation_mode,
        "allocations": allocations,
        "strategy": st.session_state.fp_maintenance_strategy,
        "projection_profile": st.session_state.fp_projection_profile,
        "rebalancing_frequency": st.session_state.fp_rebalancing_frequency,
        "scenario_quality": st.session_state.fp_scenario_quality,
        "simulation_count": model_defaults()["simulation_counts"][st.session_state.fp_scenario_quality],
        "inflation_adjust_withdrawals": bool(st.session_state.fp_inflation_adjust),
        "withdrawal_inflation_rate": float(st.session_state.fp_withdrawal_inflation_pct) / 100.0,
        "annual_management_fee": float(st.session_state.fp_management_fee_pct) / 100.0,
        "additional_contribution": parsed["contribution"],
        "random_seed": int(st.session_state.fp_random_seed),
        "include_no_withdrawal_comparison": bool(st.session_state.fp_include_no_withdrawal),
        "show_extended_range": False,
        "capital_market_assumption_date": st.session_state.fp_cma_date.isoformat(),
        "forecast_start_year": int(st.session_state.fp_forecast_start_year),
    }, parse_errors


def _format_summary_value(metric: str, value) -> str:
    if value is None or value == "":
        return "N/A"
    if isinstance(value, (int, float, np.number)):
        if "Score" in metric:
            return f"{float(value):,.1f} / 100"
        if any(token in metric for token in ("Probability", "Percentage", "Drawdown", "CAGR")):
            return f"{float(value):,.2f}%"
        if metric == "Median Depletion Year":
            return str(int(value))
        return f"${float(value):,.2f}"
    return str(value)


def _summary_metrics(summary: dict, include_no_withdrawal: bool) -> list[str]:
    metrics = [
        "Starting Investment", "Forecast Period", "Selected Holdings", "Allocation",
        "P10 Ending Balance", "P25 Ending Balance", "P50 Ending Balance", "P75 Ending Balance", "P90 Ending Balance",
        "Median Total Investment Profit", "Median Total Wealth Profit", "Median Actual Withdrawals Received",
        "Withdrawal Shortfall", "Full-Withdrawal Success Probability", "Depletion Probability", "Median Depletion Year",
    ]
    if summary.get("Median Depletion Month and Year") is not None:
        metrics.append("Median Depletion Month and Year")
    if include_no_withdrawal:
        metrics.extend(["Median No-Withdrawal Ending Balance", "Median No-Withdrawal CAGR"])
    metrics.extend([
        "Best Modeled Year", "Worst Modeled Year", "Maximum Projected Drawdown", "Positive-Year Percentage",
    ])
    if summary.get("Positive-Month Percentage") is not None:
        metrics.append("Positive-Month Percentage")
    metrics.extend(["Projection Calibration Score", "Model Confidence", "Projection Confidence Explanation"])
    return metrics


def _render_summary(result: dict) -> None:
    strategies = result.get("strategies") or {}
    include_no_withdrawal = bool((result.get("inputs") or {}).get("include_no_withdrawal_comparison"))
    columns = st.columns(len(strategies)) if len(strategies) > 1 else [st.container()]
    for column, (strategy, payload) in zip(columns, strategies.items()):
        summary = payload.get("summary") or {}
        color_class = "fp-rb" if strategy == "Rebalanced" else "fp-nr"
        cards = []
        for metric in _summary_metrics(summary, include_no_withdrawal):
            value = _format_summary_value(metric, summary.get(metric))
            cards.append(
                '<div class="fp-summary-card">'
                f'<span>{escape(metric)}</span><b>{escape(value)}</b>'
                '</div>'
            )
        with column:
            st.markdown(
                f'<section class="fp-strategy-summary {color_class}"><h3>{escape(strategy)}</h3>'
                '<div class="fp-summary-grid">' + "".join(cards) + "</div></section>",
                unsafe_allow_html=True,
            )
    st.info("Most useful planning range: P25-P75. Downside planning: P10. Central estimate: P50. P90 is a high-upside outcome, not the expected result.")


def _render_market_environment(result: dict) -> None:
    state = result.get("current_market_state") or {}
    metadata = result.get("metadata") or {}
    probabilities = state.get("regime_probabilities") or {}
    st.markdown("### Current market environment")
    st.caption(
        f"Live adaptive status: {metadata.get('live_data_status', 'UNKNOWN')} - "
        f"regime score {float(state.get('regime_score') or 0):.1f}/100 - retrieved {state.get('retrieved_at') or 'Not available'}"
    )
    cards = {
        "Bear probability": f"{float(probabilities.get('Bear') or 0):.2f}%",
        "Normal probability": f"{float(probabilities.get('Normal') or 0):.2f}%",
        "Bull probability": f"{float(probabilities.get('Bull') or 0):.2f}%",
        "Market trend": state.get("market_trend", "Unknown"),
        "Volatility": state.get("volatility_environment", "Unknown"),
        "Valuation": state.get("valuation_environment", "Unknown"),
        "Earnings trend": state.get("earnings_trend", "Unknown"),
        "Interest-rate environment": state.get("interest_rate_environment", "Unknown"),
        "Portfolio correlation risk": state.get("portfolio_correlation_risk", "Unknown"),
        "Projection confidence": metadata.get("projection_confidence", "Unknown"),
        "Calibration score": f"{float(metadata.get('projection_calibration_score') or 0):.1f}/100",
        "Breadth above 200-day MA": f"{float(state.get('breadth_above_200_day') or 0):.1f}%",
    }
    html = "".join(
        f'<div class="fp-environment-card"><span>{escape(label)}</span><b>{escape(str(value))}</b></div>'
        for label, value in cards.items()
    )
    st.markdown('<div class="fp-environment-grid">' + html + "</div>", unsafe_allow_html=True)
    risk = state.get("portfolio_risk") or {}
    if risk:
        st.markdown(
            "**Portfolio-specific risk:** "
            f"largest sector/category {risk.get('largest_sector_or_category')} ({float(risk.get('largest_sector_or_category_weight_pct') or 0):.1f}%); "
            f"mega-cap concentration {float(risk.get('mega_cap_concentration_pct') or 0):.1f}%; "
            f"high-valuation concentration {float(risk.get('high_valuation_concentration_pct') or 0):.1f}%; "
            f"factor concentration {risk.get('factor_concentration')}. "
            f"These concentrations add approximately {float(risk.get('projection_uncertainty_increase_pct') or 0):.1f}% to modeled volatility; MarketScope does not change the selected holdings."
        )
    freshness = state.get("data_freshness") or {}
    if freshness:
        rows = [{"Data": name, "Status": item.get("status"), "Updated / Through": item.get("updated")} for name, item in freshness.items()]
        with st.expander("Live data status and freshness", expanded=False):
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def _selected_percentiles() -> list[int]:
    return [p for p in PERCENTILES if bool(st.session_state.get(f"fp_chart_p{p}"))]


def _render_chart(result: dict) -> None:
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except Exception:
        st.error("The interactive chart dependency is unavailable. Install requirements.txt and restart MarketScope.")
        return
    strategies = result.get("strategies") or {}
    names = list(strategies)
    controls = st.columns([1.6, 1.5, 1.1, 1.1])
    with controls[0]:
        visible = st.multiselect("Visible portfolio maintenance paths", names, default=names, key="fp_chart_visible_strategies") if len(names) > 1 else names
    with controls[1]:
        view = st.selectbox(
            "Graph view",
            ["Portfolio Balance", "Cumulative Wealth", "Annual Profit", "Annual Return %", "Probability Range", "Model Comparison"],
            key="fp_chart_measure",
        )
    with controls[2]:
        cumulative_withdrawals = st.toggle("Cumulative withdrawals", key="fp_chart_cumulative_withdrawals")
    with controls[3]:
        no_withdrawal = st.toggle(
            "No-withdrawal reference",
            key="fp_chart_no_withdrawal",
            disabled=not bool((result.get("inputs") or {}).get("include_no_withdrawal_comparison")),
        )
    percentile_columns = st.columns(6)
    for column, percentile in zip(percentile_columns[:5], PERCENTILES):
        with column:
            st.toggle(f"P{percentile}", key=f"fp_chart_p{percentile}")
    with percentile_columns[5]:
        probability_bands = st.toggle("Range bands", key="fp_chart_probability_bands")
    selected = _selected_percentiles()
    if not visible:
        st.warning("Select at least one portfolio maintenance path to display.")
        return
    if not selected and view != "Model Comparison":
        st.warning("Turn on at least one percentile line.")
        return

    figure = make_subplots(specs=[[{"secondary_y": True}]])
    strategy_dash = {"Rebalanced": "solid", "Non-Rebalanced": "dash"}
    if view == "Model Comparison":
        frame = result.get("model_comparison", pd.DataFrame())
        colors = {
            "Adaptive Monte Carlo Ending Balance": "#2F80ED",
            "Historical Bootstrap Ending Balance": "#F59E0B",
            "Factor/CMA Ending Balance": "#14B8A6",
            "Final Ensemble Ending Balance": "#A855F7",
        }
        for column, color in colors.items():
            if isinstance(frame, pd.DataFrame) and column in frame.columns:
                figure.add_trace(go.Scatter(x=frame["Period"].astype(str), y=frame[column], mode="lines", name=column.replace(" Ending Balance", ""), line={"color": color, "width": 3 if column.startswith("Final") else 2}), secondary_y=False)
        y_title = "Portfolio balance"
    else:
        for strategy in visible:
            frame = strategies[strategy]["chart"]
            x = frame["Period"].astype(str)
            return_suffix = "Monthly Return %" if "P50 Monthly Return %" in frame.columns else "Annual Return %"
            if view == "Probability Range" and probability_bands:
                if 10 in selected and 90 in selected:
                    figure.add_trace(go.Scatter(x=x, y=frame["P90 Ending Balance"], line={"width": 0}, showlegend=False, hoverinfo="skip"), secondary_y=False)
                    figure.add_trace(go.Scatter(x=x, y=frame["P10 Ending Balance"], line={"width": 0}, fill="tonexty", fillcolor="rgba(47,128,237,0.12)", name=f"{strategy} P10-P90", hoverinfo="skip"), secondary_y=False)
                if 25 in selected and 75 in selected:
                    figure.add_trace(go.Scatter(x=x, y=frame["P75 Ending Balance"], line={"width": 0}, showlegend=False, hoverinfo="skip"), secondary_y=False)
                    figure.add_trace(go.Scatter(x=x, y=frame["P25 Ending Balance"], line={"width": 0}, fill="tonexty", fillcolor="rgba(20,184,166,0.20)", name=f"{strategy} P25-P75", hoverinfo="skip"), secondary_y=False)
            for percentile in selected:
                if view in {"Portfolio Balance", "Probability Range"}:
                    column = f"P{percentile} Ending Balance"
                    y_title = "Portfolio balance"
                    tickprefix = "$"
                elif view == "Cumulative Wealth":
                    column = f"P{percentile} Cumulative Wealth"
                    y_title = "Cumulative wealth"
                    tickprefix = "$"
                elif view == "Annual Profit":
                    column = f"P{percentile} Profit"
                    y_title = "Period investment profit / loss"
                    tickprefix = "$"
                else:
                    column = f"P{percentile} {return_suffix}"
                    y_title = return_suffix
                    tickprefix = ""
                if column not in frame.columns:
                    continue
                custom = np.column_stack([
                    frame.get("P50 Profit", pd.Series(np.zeros(len(frame)))).astype(float),
                    frame["Actual Withdrawal"].astype(float),
                    frame["Cumulative Withdrawals"].astype(float),
                ])
                figure.add_trace(
                    go.Scatter(
                        x=x,
                        y=frame[column],
                        mode="lines+markers" if len(frame) <= 15 else "lines",
                        name=f"{strategy} P{percentile}",
                        line={"color": PERCENTILE_COLORS[percentile], "width": 3 if percentile == 50 else 2, "dash": strategy_dash[strategy]},
                        customdata=custom,
                        hovertemplate=(
                            f"<b>%{{x}} - {strategy} P{percentile}</b><br>Value: %{{y:,.2f}}"
                            "<br>P50 profit: $%{customdata[0]:+,.2f}<br>Actual withdrawal: $%{customdata[1]:,.2f}"
                            "<br>Cumulative withdrawals: $%{customdata[2]:,.2f}<extra></extra>"
                        ),
                    ), secondary_y=False,
                )
            if no_withdrawal:
                reference = strategies[strategy].get("no_withdrawal_chart", pd.DataFrame())
                if isinstance(reference, pd.DataFrame) and not reference.empty and view in {"Portfolio Balance", "Cumulative Wealth", "Probability Range"}:
                    reference_col = "P50 Cumulative Wealth" if view == "Cumulative Wealth" else "P50 Ending Balance"
                    figure.add_trace(go.Scatter(x=reference["Period"].astype(str), y=reference[reference_col], mode="lines", name=f"{strategy} no withdrawal", line={"color": "#94A3B8", "width": 2, "dash": "dot"}), secondary_y=False)
            if cumulative_withdrawals:
                figure.add_trace(go.Scatter(x=x, y=frame["Cumulative Withdrawals"], mode="lines", name=f"{strategy} cumulative withdrawals", line={"color": "#CBD5E1", "width": 1.5, "dash": "dot"}), secondary_y=True)
        if view in {"Portfolio Balance", "Cumulative Wealth", "Probability Range"}:
            figure.add_hline(y=float((result.get("inputs") or {}).get("starting_investment") or 0), line_dash="dot", line_color="#64748B", annotation_text="Starting investment")
    period_count = max((len(strategies[name]["chart"]) for name in visible), default=1)
    figure.update_layout(
        height=590,
        margin={"l": 20, "r": 20, "t": 50, "b": 55},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(8,18,33,0.55)",
        font={"color": "#E2E8F0"},
        hovermode="x unified",
        legend={"orientation": "h", "y": 1.18, "x": 0},
        xaxis={"title": "Forecast period", "type": "category", "nticks": min(14, period_count)},
    )
    figure.update_yaxes(title_text=y_title, tickprefix=(tickprefix if view != "Model Comparison" else "$"), separatethousands=True, secondary_y=False)
    figure.update_yaxes(title_text="Cumulative withdrawals", tickprefix="$", separatethousands=True, secondary_y=True)
    st.plotly_chart(figure, width="stretch", key="future_projection_performance_chart")


def _table_columns(frame: pd.DataFrame, monthly: bool) -> list[str]:
    columns = ["Year"]
    if monthly:
        columns.append("Month")
    columns.append("Beginning Balance")
    return_suffix = "Monthly Return %" if monthly else "Annual Return %"
    for percentile in PERCENTILES:
        columns.extend([f"P{percentile} Profit", f"P{percentile} {return_suffix}"])
    columns.extend([
        "Requested Withdrawal", "Actual Withdrawal", "Withdrawal Shortfall",
        "Contribution" if monthly else "Additional Contribution", "Fees", "Median Net Change",
    ])
    columns.extend([f"P{percentile} Ending Balance" for percentile in PERCENTILES])
    columns.extend(["Cumulative Withdrawals", "Total Wealth Profit", "Depletion Probability", "Status"])
    return [column for column in columns if column in frame.columns]


def _style_projection_table(frame: pd.DataFrame):
    currency_columns = [column for column in frame.columns if any(token in column for token in ("Balance", "Profit", "Withdrawal", "Contribution", "Fees", "Net Change"))]
    percent_columns = [column for column in frame.columns if "Return" in column or "Probability" in column]
    formats = {column: "${:,.2f}" for column in currency_columns}
    formats.update({column: "{:+,.2f}%" if "Return" in column else "{:,.2f}%" for column in percent_columns})

    def color_value(value):
        if isinstance(value, str):
            if "Depleted" in value:
                return "color:#F87171;font-weight:700"
            if "Partial" in value:
                return "color:#FBBF24;font-weight:700"
            if value == "Active":
                return "color:#34D399;font-weight:700"
        if isinstance(value, (int, float, np.number)):
            return "color:#34D399" if float(value) > 0 else ("color:#F87171" if float(value) < 0 else "")
        return ""

    styled = frame.style.format(formats, na_rep="N/A")
    colored = [column for column in frame.columns if "Profit" in column or column in {"Median Net Change", "Status"}]
    return styled.map(color_value, subset=colored)


def _render_strategy_table(strategy: str, payload: dict, monthly: bool) -> None:
    frame = payload.get("table", pd.DataFrame())
    if frame.empty:
        st.warning(f"No {strategy.lower()} projection rows are available.")
        return
    display = frame[_table_columns(frame, monthly)].copy()
    st.dataframe(_style_projection_table(display), width="stretch", hide_index=True, height=min(720, 74 + len(display) * 34), key=f"fp_{strategy.lower().replace('-', '_')}_projection_table")
    with st.expander(f"{strategy} holding-level detail", expanded=False):
        details = payload.get("holding_details", pd.DataFrame())
        if details.empty:
            st.info("Holding-level detail is unavailable.")
        else:
            st.dataframe(details, width="stretch", hide_index=True, height=min(650, 74 + len(details) * 30), key=f"fp_{strategy.lower().replace('-', '_')}_holding_details")


def _render_results_tables(result: dict) -> None:
    strategies = result.get("strategies") or {}
    monthly = (result.get("metadata") or {}).get("output_frequency") == "Monthly"
    if len(strategies) == 2:
        rb_tab, nr_tab, side_tab = st.tabs(["Rebalanced", "Non-Rebalanced", "Side-by-Side"])
        with rb_tab:
            _render_strategy_table("Rebalanced", strategies["Rebalanced"], monthly)
        with nr_tab:
            _render_strategy_table("Non-Rebalanced", strategies["Non-Rebalanced"], monthly)
        with side_tab:
            comparison = result.get("comparison", pd.DataFrame())
            st.dataframe(comparison, width="stretch", hide_index=True, height=min(720, 74 + len(comparison) * 34))
    else:
        strategy = next(iter(strategies), None)
        if strategy:
            only_tab, = st.tabs([strategy])
            with only_tab:
                _render_strategy_table(strategy, strategies[strategy], monthly)


def _render_exports(result: dict) -> None:
    from runtime_performance import projection_exports
    seed = int((result.get("metadata") or {}).get("random_seed") or 0)
    columns = st.columns(3)
    try:
        excel_bytes, csv_bytes, pdf_bytes = projection_exports(result)
    except Exception:
        st.error("One or more exports could not be generated. Re-run the projection or verify export dependencies.")
        return
    columns[0].download_button("Download Excel", data=excel_bytes, file_name=f"MarketScope_Future_Projection_seed_{seed}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
    columns[1].download_button("Download CSV", data=csv_bytes, file_name=f"MarketScope_Future_Projection_seed_{seed}.csv", mime="text/csv", width="stretch")
    columns[2].download_button("Download PDF", data=pdf_bytes, file_name=f"MarketScope_Future_Projection_seed_{seed}.pdf", mime="application/pdf", width="stretch")


def render_future_projection(
    market: pd.DataFrame,
    annual_year_columns: list[str] | tuple[str, ...],
    latest_completed_year: int,
    data_as_of: str,
    model_as_of: str,
    monthly_loader: Callable[[tuple[str, ...], tuple[str, ...]], dict] | None = None,
    live_loader: Callable[[tuple[str, ...]], dict] | None = None,
    logo_loader: Callable[[tuple[str, ...]], dict] | None = None,
    current_simulator_payload: dict | None = None,
) -> None:
    """Render the Future Projection workspace without touching historical simulators."""

    _initialize_state(int(latest_completed_year))
    pending = st.session_state.pop("future_projection_pending_payload", None)
    if pending:
        _apply_payload(pending)
        st.success("Loaded the selected MarketScope simulator portfolio. Review assumptions, then run the projection.")

    st.markdown('<div class="fp-title">FUTURE PROJECTION</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="fp-disclaimer">{escape(DISCLAIMER)}</div>', unsafe_allow_html=True)
    meta_values = {
        "Historical data as of": data_as_of or "Not available",
        "Model as of": model_as_of,
        "First forecast year": int(st.session_state.fp_forecast_start_year),
        "Completed history through": int(latest_completed_year),
    }
    st.markdown(
        '<div class="fp-meta-grid">' + "".join(
            f'<div class="fp-meta-card"><span>{escape(label)}</span><b>{escape(str(value))}</b></div>'
            for label, value in meta_values.items()
        ) + "</div>",
        unsafe_allow_html=True,
    )

    lookup = market.copy()
    lookup["Symbol"] = lookup["Symbol"].astype(str).str.upper()
    lookup = lookup.drop_duplicates("Symbol", keep="last").set_index("Symbol", drop=False)
    all_symbols = sorted(lookup.index.tolist())

    with st.container(border=True):
        st.markdown("### Projection inputs")
        first_row = st.columns([1.3, 1.2, 1.25, 1.0])
        with first_row[0]:
            st.text_input("Starting Investment", key="fp_starting_investment_text", help="Minimum $1,000. Commas and currency formatting are accepted.")
        with first_row[1]:
            st.segmented_control("Withdrawal Frequency", ["No Withdrawal", "Yearly", "Monthly"], key="fp_withdrawal_frequency")
        with first_row[2]:
            frequency = st.session_state.fp_withdrawal_frequency
            if frequency == "Yearly":
                st.text_input("Annual Withdrawal", key="fp_annual_withdrawal_text")
                try:
                    st.caption(f"Annualized withdrawal: {_money_text(parse_currency(st.session_state.fp_annual_withdrawal_text))}")
                except ProjectionValidationError:
                    st.caption("Enter a valid annual currency amount.")
            elif frequency == "Monthly":
                st.text_input("Monthly Withdrawal", key="fp_monthly_withdrawal_text")
                try:
                    st.caption(f"Annualized withdrawal: {_money_text(parse_currency(st.session_state.fp_monthly_withdrawal_text) * 12.0)}")
                except ProjectionValidationError:
                    st.caption("Enter a valid monthly currency amount.")
            else:
                st.text_input("Withdrawal Amount", value="$0", disabled=True, key="fp_no_withdrawal_display")
                st.caption("No portfolio withdrawals will be requested.")
        with first_row[3]:
            st.radio("Withdrawal Timing", ["End of period", "Beginning of period"], key="fp_withdrawal_timing", disabled=frequency == "No Withdrawal")

        second_row = st.columns([1.0, 1.0, 1.25, 1.1, 1.25])
        with second_row[0]:
            min_start = int(latest_completed_year) + 1
            st.number_input("Projection Start Year", min_value=min_start, max_value=min_start + 50, step=1, key="fp_forecast_start_year")
        with second_row[1]:
            st.number_input("Future Years", min_value=1, max_value=50, step=1, key="fp_future_years")
            start = int(st.session_state.fp_forecast_start_year)
            st.caption(f"Forecast range: {start}-{start + int(st.session_state.fp_future_years) - 1}")
        with second_row[2]:
            st.segmented_control("Portfolio Maintenance", ["Rebalanced", "Non-Rebalanced", "Both"], key="fp_maintenance_strategy")
        with second_row[3]:
            st.selectbox("Rebalancing Frequency", ["Yearly", "Quarterly", "Monthly"], key="fp_rebalancing_frequency", disabled=st.session_state.fp_maintenance_strategy == "Non-Rebalanced")
        with second_row[4]:
            quality = st.selectbox("Scenario Quality", ["Standard", "Advanced", "High Precision"], key="fp_scenario_quality", format_func=lambda value: f"{value} - {model_defaults()['simulation_counts'][value]:,} simulations")
            if quality == "High Precision":
                st.warning("High Precision runs 50,000 simulations and may take longer.")

        profile = st.selectbox("Projection Strategy", ["AUTO", "Conservative", "Balanced", "Growth", "Stress Test"], key="fp_projection_profile")
        st.caption(PROFILE_HELP[profile])

        st.markdown("#### Portfolio holdings")
        st.multiselect(
            "Stocks & ETFs",
            options=all_symbols,
            key="fp_holdings",
            format_func=lambda symbol, _lookup=lookup: _holding_option_label(symbol, _lookup),
            placeholder="Search ticker or company/fund name and add as many holdings as needed...",
            help="At least one holding is required. There is no fixed four-holding limit and duplicates are prevented by the selector.",
        )
        holdings = [str(symbol).upper() for symbol in st.session_state.fp_holdings]
        _render_selected_holding_cards(holdings, lookup, logo_loader)

        action_columns = st.columns([1, 1.5, 3])
        action_columns[0].button("Clear Portfolio", width="stretch", on_click=_clear_portfolio)
        can_use_current = bool(current_simulator_payload and current_simulator_payload.get("holdings"))
        action_columns[1].button(
            "Use Current Simulator Portfolio", disabled=not can_use_current, width="stretch",
            help="Loads the current simulator holdings, amount, withdrawals, and allocation without regenerating rankings.",
            on_click=_apply_payload, args=(current_simulator_payload or {},),
        )

        st.segmented_control("Allocation", ["Equal Split", "Custom Allocation"], key="fp_allocation_mode")
        if st.session_state.fp_allocation_mode == "Equal Split":
            equal = 100.0 / len(holdings) if holdings else 0.0
            st.caption(f"Equal Split assigns {equal:.6f}% to each of {len(holdings)} holding(s). Live total: {100.0 if holdings else 0.0:.2f}%")
        else:
            for offset in range(0, len(holdings), 3):
                columns = st.columns(min(3, len(holdings) - offset))
                for column, symbol in zip(columns, holdings[offset:offset + 3]):
                    key = _allocation_key(symbol)
                    _state_default(key, 100.0 / len(holdings) if holdings else 0.0)
                    with column:
                        st.number_input(f"{symbol} allocation %", min_value=0.0, max_value=100.0, step=0.25, format="%.4f", key=key)
            allocation_total = sum(float(st.session_state.get(_allocation_key(symbol)) or 0.0) for symbol in holdings)
            tone = "fp-total-valid" if abs(allocation_total - 100.0) <= 1e-8 else "fp-total-invalid"
            st.markdown(f'<div class="fp-allocation-total {tone}">Live allocation total: {allocation_total:.4f}%</div>', unsafe_allow_html=True)

        with st.expander("Advanced Settings", expanded=False):
            advanced = st.columns(3)
            with advanced[0]:
                st.toggle("Inflation-adjust withdrawals", key="fp_inflation_adjust")
                st.number_input("Annual withdrawal inflation rate (%)", min_value=-99.0, max_value=25.0, step=0.1, format="%.2f", key="fp_withdrawal_inflation_pct", disabled=not st.session_state.fp_inflation_adjust)
                st.number_input("Annual management fee (%)", min_value=0.0, max_value=99.0, step=0.05, format="%.3f", key="fp_management_fee_pct")
            with advanced[1]:
                contribution_label = "Additional monthly contribution" if frequency == "Monthly" else "Additional annual contribution"
                st.text_input(contribution_label, key="fp_contribution_text")
                st.number_input("Random seed", min_value=0, max_value=2_147_483_647, step=1, key="fp_random_seed")
                st.toggle("Include no-withdrawal comparison", key="fp_include_no_withdrawal")
            with advanced[2]:
                st.date_input("Capital-market assumption date", key="fp_cma_date")
                cma = capital_market_assumptions()["broad_market_annual_geometric_return"]
                st.markdown(
                    "**Expected-return model details**  \n"
                    f"Broad-market anchor: {float(cma['value']) * 100:.2f}%  \nSource: {cma['source']}  \n"
                    f"As of: {cma['as_of_date']}  \nLast updated: {cma['last_updated_date']}  \n"
                    "The live engine uses bounded valuation, fundamental, momentum, rates, volatility, and correlation adjustments with heavy shrinkage."
                )

    projection_inputs, parse_errors = _build_inputs()
    validation_errors, validation_warnings = validate_projection_inputs(projection_inputs, market)
    all_errors = [*parse_errors, *validation_errors]
    for warning in validation_warnings:
        st.warning(warning)
    if len(holdings) > 40:
        st.warning("A very large portfolio can take longer at Advanced or High Precision quality, but the selection is allowed.")
    if all_errors:
        st.error("Projection cannot run yet: " + " ".join(dict.fromkeys(all_errors)))

    run_columns = st.columns([1.5, 1, 4])
    run_clicked = run_columns[0].button("Run Projection", type="primary", disabled=bool(all_errors) or bool(st.session_state.fp_running), width="stretch")
    run_columns[1].button("Reset", disabled=bool(st.session_state.fp_running), width="stretch", on_click=_reset_projection)
    if run_clicked:
        st.session_state.fp_running = True
        monthly_payload = {}
        live_context = {}
        needs_monthly = projection_inputs["withdrawal_frequency"] == "Monthly" or (projection_inputs["strategy"] in {"Rebalanced", "Both"} and projection_inputs["rebalancing_frequency"] in {"Quarterly", "Monthly"})
        if needs_monthly and monthly_loader is not None:
            with st.spinner("Loading actual monthly return history and identifying explicit fallback periods..."):
                try:
                    monthly_payload = monthly_loader(tuple(projection_inputs["holdings"]), tuple(annual_year_columns)) or {}
                except Exception:
                    monthly_payload = {"unavailable": True, "returns": {}, "reason": "Actual monthly history loader did not complete."}
        if live_loader is not None:
            with st.spinner("Building the current market state from recent market, fundamental, volatility, and official macro data..."):
                try:
                    live_context = live_loader(tuple(projection_inputs["holdings"])) or {}
                except Exception as exc:
                    live_context = {"failures": [f"Live adaptive loader did not complete ({type(exc).__name__})."]}
        key = projection_cache_key(projection_inputs, market, annual_year_columns, monthly_payload, data_as_of, live_context)
        cache = dict(st.session_state.fp_result_cache or {})
        if key in cache:
            st.session_state.fp_result = cache[key]
            st.session_state.fp_running = False
            st.success("Loaded an identical projection from the in-session result cache.")
        else:
            progress_bar = st.progress(0.0, text="Preparing projection worker...")
            progress_events: queue.Queue = queue.Queue()

            def report_progress(completed: int, total: int, label: str) -> None:
                progress_events.put((completed, total, label))

            try:
                with ThreadPoolExecutor(max_workers=1, thread_name_prefix="marketscope-future") as executor:
                    future = executor.submit(run_future_projection, market, projection_inputs, annual_year_columns, monthly_payload, data_as_of, model_as_of, report_progress, live_context)
                    while not future.done():
                        latest = None
                        while True:
                            try:
                                latest = progress_events.get_nowait()
                            except queue.Empty:
                                break
                        if latest:
                            completed, total, label = latest
                            progress_bar.progress(min(0.99, completed / max(1, total)), text=f"{label} - simulations completed: {completed:,} / {total:,}")
                        time.sleep(0.04)
                    result = future.result()
                progress_bar.progress(1.0, text=f"Simulations completed: {projection_inputs['simulation_count']:,} / {projection_inputs['simulation_count']:,}")
                cache[key] = result
                while len(cache) > 5:
                    cache.pop(next(iter(cache)))
                st.session_state.fp_result_cache = cache
                st.session_state.fp_result = result
                st.success(f"Projection complete - {projection_inputs['simulation_count']:,} deterministic ensemble simulations.")
            except ProjectionValidationError as exc:
                st.error(str(exc))
            except Exception as exc:
                print(f"Future Projection internal error: {type(exc).__name__}: {exc}")
                st.error("The projection could not be completed. Verify the selected holdings and historical data, then try again.")
            finally:
                st.session_state.fp_running = False

    result = st.session_state.get("fp_result")
    if not result:
        st.info("Select at least one holding and choose Run Projection to generate probabilistic results.")
        return
    metadata = result.get("metadata") or {}
    st.markdown("### Projection results")
    st.caption(
        f"Data as of {metadata.get('data_as_of')} - model as of {metadata.get('model_as_of')} - "
        f"{int(metadata.get('simulation_count') or 0):,} simulations - fixed seed {metadata.get('random_seed')} - "
        f"{metadata.get('base_frequency')} model / {metadata.get('output_frequency')} results - {metadata.get('live_data_status')}"
    )
    for warning in result.get("warnings") or []:
        st.warning(warning)
    _render_market_environment(result)
    _render_summary(result)
    st.markdown("### Performance projection")
    _render_chart(result)
    st.markdown("### Detailed projection tables")
    _render_results_tables(result)
    with st.expander("Model assumptions, diagnostics, sources, backtests, and limitations", expanded=False):
        st.markdown("#### Model assumptions")
        assumptions = result.get("model_assumptions", pd.DataFrame()).copy()
        if "Value" in assumptions.columns:
            assumptions["Value"] = assumptions["Value"].map(str)
        st.dataframe(assumptions, width="stretch", hide_index=True)
        st.markdown("#### Stock/ETF assumptions and data quality")
        st.dataframe(result.get("holding_assumptions", pd.DataFrame()), width="stretch", hide_index=True)
        st.markdown("#### Walk-forward validation")
        st.dataframe(result.get("model_validation_metrics", pd.DataFrame()), width="stretch", hide_index=True)
        with st.expander("Walk-forward observations", expanded=False):
            st.dataframe(result.get("walk_forward_validation", pd.DataFrame()), width="stretch", hide_index=True)
        st.markdown("#### Auditable projection record")
        st.json(result.get("audit") or {})
        st.markdown("#### Diagnostics")
        st.json(result.get("diagnostics") or {})
        st.markdown("#### Sources and limitations")
        for limitation in result.get("limitations") or []:
            st.markdown(f"- {limitation}")
    st.markdown("### Export")
    _render_exports(result)
