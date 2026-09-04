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
    normalize_projection_inputs,
    parse_currency,
    projection_cache_key,
    run_future_projection,
    validate_projection_inputs,
)
from future_projection_config import capital_market_assumptions, model_defaults


DISCLAIMER = (
    "Future projections are hypothetical estimates based on historical data and model assumptions. "
    "They are not guaranteed results or individualized investment advice."
)


def _money_text(value: float) -> str:
    return f"${float(value):,.2f}"


def _state_default(key: str, value) -> None:
    if key not in st.session_state:
        st.session_state[key] = value


def _initialize_state() -> None:
    defaults = {
        "fp_starting_investment_text": "$400,000",
        "fp_withdrawal_frequency": "Yearly",
        "fp_annual_withdrawal_text": "$200,000",
        "fp_monthly_withdrawal_text": "$16,666.67",
        "fp_withdrawal_timing": "End of period",
        "fp_future_years": 10,
        "fp_allocation_mode": "Equal Split",
        "fp_strategy": "Both",
        "fp_rebalancing_frequency": "Yearly",
        "fp_scenario_quality": "Advanced",
        "fp_inflation_adjust": False,
        "fp_withdrawal_inflation_pct": 2.5,
        "fp_management_fee_pct": 0.0,
        "fp_contribution_text": "$0",
        "fp_random_seed": 20260903,
        "fp_include_no_withdrawal": True,
        "fp_show_extended": False,
        "fp_result": None,
        "fp_result_cache": {},
        "fp_running": False,
        "fp_chart_bands": True,
        "fp_chart_cumulative_withdrawals": False,
        "fp_chart_no_withdrawal": True,
        "fp_chart_measure": "Portfolio Balance",
    }
    cma_date = capital_market_assumptions()["broad_market_annual_geometric_return"]["as_of_date"]
    defaults["fp_cma_date"] = date.fromisoformat(cma_date)
    for idx in range(1, 5):
        defaults[f"fp_holding_{idx}"] = ""
        defaults[f"fp_allocation_{idx}"] = 25.0
    for key, value in defaults.items():
        _state_default(key, value)


def _apply_payload(payload: dict) -> None:
    payload = dict(payload or {})
    holdings = list(payload.get("holdings") or [])[:4]
    st.session_state.fp_starting_investment_text = _money_text(payload.get("starting_investment") or 400_000.0)
    st.session_state.fp_withdrawal_frequency = str(payload.get("withdrawal_frequency") or "No Withdrawal")
    st.session_state.fp_annual_withdrawal_text = _money_text(payload.get("annual_withdrawal") or 0.0)
    st.session_state.fp_monthly_withdrawal_text = _money_text(payload.get("monthly_withdrawal") or 0.0)
    st.session_state.fp_withdrawal_timing = str(payload.get("withdrawal_timing") or "End of period")
    st.session_state.fp_future_years = int(payload.get("future_years") or 10)
    st.session_state.fp_allocation_mode = str(payload.get("allocation_mode") or "Equal Split")
    st.session_state.fp_strategy = str(payload.get("strategy") or "Both")
    st.session_state.fp_rebalancing_frequency = str(payload.get("rebalancing_frequency") or "Yearly")
    allocations = dict(payload.get("allocations") or {})
    for idx in range(1, 5):
        symbol = str(holdings[idx - 1]).upper() if idx <= len(holdings) else ""
        st.session_state[f"fp_holding_{idx}"] = symbol
        st.session_state[f"fp_allocation_{idx}"] = float(allocations.get(symbol, 25.0))
    st.session_state.fp_result = None


def _clear_portfolio() -> None:
    for idx in range(1, 5):
        st.session_state[f"fp_holding_{idx}"] = ""
        st.session_state[f"fp_allocation_{idx}"] = 25.0
    st.session_state.fp_result = None


def _reset_projection() -> None:
    for key in list(st.session_state.keys()):
        if str(key).startswith("fp_"):
            del st.session_state[key]
    _initialize_state()


def _holding_option_label(symbol: str, lookup: pd.DataFrame) -> str:
    if not symbol:
        return "- Select a stock or ETF -"
    if symbol not in lookup.index:
        return symbol
    row = lookup.loc[symbol]
    if isinstance(row, pd.DataFrame):
        row = row.iloc[-1]
    name = str(row.get("Name") or symbol)
    instrument_type = str(row.get("Type") or "Stock")
    category = holding_category(row)
    return f"{symbol} - {name} | {instrument_type} | {category}"


def _render_selected_holding_cards(
    holdings: list[str],
    lookup: pd.DataFrame,
    logo_loader: Callable[[tuple[str, ...]], dict] | None,
) -> None:
    selected = [symbol for symbol in holdings if symbol and symbol in lookup.index]
    logos = {}
    if selected and logo_loader is not None:
        try:
            logos = logo_loader(tuple(selected)) or {}
        except Exception:
            logos = {}
    columns = st.columns(4)
    for idx, column in enumerate(columns):
        symbol = holdings[idx] if idx < len(holdings) else ""
        if not symbol or symbol not in lookup.index:
            with column:
                st.caption(f"Holding {idx + 1}: not selected")
            continue
        row = lookup.loc[symbol]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[-1]
        name = str(row.get("Name") or symbol)
        instrument_type = str(row.get("Type") or "Stock")
        category = holding_category(row)
        logo = str(logos.get(symbol) or "")
        image = (
            f'<img src="{escape(logo, quote=True)}" alt="{escape(symbol)} logo">'
            if logo.startswith(("https://", "http://")) else f'<span class="fp-logo-fallback">{escape(symbol[:2])}</span>'
        )
        with column:
            st.markdown(
                '<div class="fp-holding-card">'
                f'{image}<div><b>{escape(symbol)}</b><span>{escape(name)}</span>'
                f'<small>{escape(instrument_type)} - {escape(category)}</small></div></div>',
                unsafe_allow_html=True,
            )


def _build_inputs(latest_completed_year: int) -> tuple[dict, list[str]]:
    parse_errors = []
    try:
        starting = parse_currency(st.session_state.fp_starting_investment_text)
    except ProjectionValidationError as exc:
        starting = 0.0
        parse_errors.append(f"Starting Investment: {exc}")
    try:
        annual = parse_currency(st.session_state.fp_annual_withdrawal_text)
    except ProjectionValidationError as exc:
        annual = -1.0
        parse_errors.append(f"Annual Withdrawal: {exc}")
    try:
        monthly = parse_currency(st.session_state.fp_monthly_withdrawal_text)
    except ProjectionValidationError as exc:
        monthly = -1.0
        parse_errors.append(f"Monthly Withdrawal: {exc}")
    try:
        contribution = parse_currency(st.session_state.fp_contribution_text)
    except ProjectionValidationError as exc:
        contribution = -1.0
        parse_errors.append(f"Additional contribution: {exc}")
    holdings = [str(st.session_state.get(f"fp_holding_{idx}") or "").upper() for idx in range(1, 5)]
    allocations = {
        symbol: (25.0 if st.session_state.fp_allocation_mode == "Equal Split" else float(st.session_state.get(f"fp_allocation_{idx}") or 0.0))
        for idx, symbol in enumerate(holdings, start=1)
        if symbol
    }
    return {
        "starting_investment": starting,
        "withdrawal_frequency": st.session_state.fp_withdrawal_frequency,
        "annual_withdrawal": annual,
        "monthly_withdrawal": monthly,
        "withdrawal_timing": st.session_state.fp_withdrawal_timing,
        "future_years": int(st.session_state.fp_future_years),
        "holdings": holdings,
        "allocation_mode": st.session_state.fp_allocation_mode,
        "allocations": allocations,
        "strategy": st.session_state.fp_strategy,
        "rebalancing_frequency": st.session_state.fp_rebalancing_frequency,
        "scenario_quality": st.session_state.fp_scenario_quality,
        "simulation_count": model_defaults()["simulation_counts"][st.session_state.fp_scenario_quality],
        "inflation_adjust_withdrawals": bool(st.session_state.fp_inflation_adjust),
        "withdrawal_inflation_rate": float(st.session_state.fp_withdrawal_inflation_pct) / 100.0,
        "annual_management_fee": float(st.session_state.fp_management_fee_pct) / 100.0,
        "additional_contribution": contribution,
        "random_seed": int(st.session_state.fp_random_seed),
        "include_no_withdrawal_comparison": bool(st.session_state.fp_include_no_withdrawal),
        "show_extended_range": bool(st.session_state.fp_show_extended),
        "capital_market_assumption_date": st.session_state.fp_cma_date.isoformat(),
        "forecast_start_year": int(latest_completed_year) + 1,
    }, parse_errors


def _format_summary_value(metric: str, value) -> str:
    if value is None or value == "":
        return "N/A"
    if isinstance(value, (int, float, np.number)):
        if "Probability" in metric or "Percentage" in metric or "Drawdown" in metric or "CAGR" in metric:
            return f"{float(value):,.2f}%"
        if metric == "Median Depletion Year":
            return str(int(value))
        return f"${float(value):,.2f}"
    return str(value)


def _summary_metrics(summary: dict, show_extended: bool, include_no_withdrawal: bool) -> list[str]:
    metrics = [
        "Starting Investment", "Forecast Period", "Selected Holdings", "Allocation",
        "Median Ending Balance", "P10 Ending Balance", "P90 Ending Balance",
    ]
    if show_extended:
        metrics.extend(["P5 Ending Balance", "P95 Ending Balance"])
    metrics.extend([
        "Median Total Investment Profit", "Median Total Wealth Profit",
        "Median Actual Withdrawals Received", "Withdrawal Shortfall",
        "Full-Withdrawal Success Probability", "Depletion Probability",
        "Median Depletion Year",
    ])
    if summary.get("Median Depletion Month and Year") is not None:
        metrics.append("Median Depletion Month and Year")
    if include_no_withdrawal:
        metrics.extend(["Median No-Withdrawal Ending Balance", "Median No-Withdrawal CAGR"])
    metrics.extend([
        "Best Modeled Year", "Worst Modeled Year", "Maximum Projected Drawdown",
        "Positive-Year Percentage",
    ])
    if summary.get("Positive-Month Percentage") is not None:
        metrics.append("Positive-Month Percentage")
    metrics.append("Model Confidence")
    return metrics


def _render_summary(result: dict) -> None:
    strategies = result.get("strategies") or {}
    show_extended = bool((result.get("inputs") or {}).get("show_extended_range"))
    include_no_withdrawal = bool((result.get("inputs") or {}).get("include_no_withdrawal_comparison"))
    columns = st.columns(len(strategies)) if len(strategies) > 1 else [st.container()]
    for column, (strategy, payload) in zip(columns, strategies.items()):
        summary = payload.get("summary") or {}
        color_class = "fp-rb" if strategy == "Rebalanced" else "fp-nr"
        cards = []
        for metric in _summary_metrics(summary, show_extended, include_no_withdrawal):
            cards.append(
                '<div class="fp-summary-card">'
                f'<span>{escape(metric)}</span><b>{escape(_format_summary_value(metric, summary.get(metric)))}</b>'
                '</div>'
            )
        with column:
            st.markdown(
                f'<section class="fp-strategy-summary {color_class}"><h3>{escape(strategy)}</h3>'
                '<div class="fp-summary-grid">' + "".join(cards) + "</div></section>",
                unsafe_allow_html=True,
            )


def _render_chart(result: dict) -> None:
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except Exception:
        st.error("The interactive chart dependency is unavailable. Install the packages in requirements.txt and restart MarketScope.")
        return
    strategies = result.get("strategies") or {}
    names = list(strategies)
    controls = st.columns([1.8, 1.1, 1.1, 1.1, 1.4])
    with controls[0]:
        visible = st.multiselect(
            "Visible strategies",
            options=names,
            default=names,
            key="fp_chart_visible_strategies",
        ) if len(names) > 1 else names
    with controls[1]:
        bands = st.toggle("Confidence bands", key="fp_chart_bands")
    with controls[2]:
        cumulative_withdrawals = st.toggle("Cumulative withdrawals", key="fp_chart_cumulative_withdrawals")
    with controls[3]:
        no_withdrawal = st.toggle(
            "No-withdrawal reference",
            key="fp_chart_no_withdrawal",
            disabled=not bool((result.get("inputs") or {}).get("include_no_withdrawal_comparison")),
        )
    with controls[4]:
        measure = st.segmented_control(
            "Chart measure",
            ["Portfolio Balance", "Cumulative Wealth"],
            key="fp_chart_measure",
        )
    if not visible:
        st.warning("Select at least one strategy to display the performance chart.")
        return
    figure = make_subplots(specs=[[{"secondary_y": True}]])
    colors = {"Rebalanced": "#2F80ED", "Non-Rebalanced": "#F59E0B"}
    rgba = {"Rebalanced": "rgba(47,128,237,0.16)", "Non-Rebalanced": "rgba(245,158,11,0.16)"}
    if measure == "Cumulative Wealth":
        median_col = "Cumulative Wealth"
        p10_col, p90_col = "P10 Cumulative Wealth", "P90 Cumulative Wealth"
        p5_col, p95_col = "P5 Cumulative Wealth", "P95 Cumulative Wealth"
    else:
        median_col = "Median Ending Balance"
        p10_col, p90_col = "P10 Ending Balance", "P90 Ending Balance"
        p5_col, p95_col = "P5 Ending Balance", "P95 Ending Balance"
    show_extended = bool((result.get("inputs") or {}).get("show_extended_range"))
    for strategy in visible:
        frame = strategies[strategy]["chart"]
        x = frame["Period"].astype(str)
        color = colors[strategy]
        if bands:
            if show_extended:
                figure.add_trace(go.Scatter(x=x, y=frame[p95_col], line={"width": 0}, showlegend=False, hoverinfo="skip"), secondary_y=False)
                figure.add_trace(go.Scatter(x=x, y=frame[p5_col], line={"width": 0}, fill="tonexty", fillcolor=rgba[strategy].replace("0.16", "0.07"), name=f"{strategy} P5-P95", hoverinfo="skip"), secondary_y=False)
            figure.add_trace(go.Scatter(x=x, y=frame[p90_col], line={"width": 0}, showlegend=False, hoverinfo="skip"), secondary_y=False)
            figure.add_trace(go.Scatter(x=x, y=frame[p10_col], line={"width": 0}, fill="tonexty", fillcolor=rgba[strategy], name=f"{strategy} P10-P90", hoverinfo="skip"), secondary_y=False)
        return_col = "Median Monthly Return" if "Median Monthly Return" in frame.columns else "Median Portfolio Return"
        custom = np.column_stack([
            frame[return_col].astype(float),
            frame["Median Gross Profit"].astype(float),
            frame["Actual Withdrawal"].astype(float),
            frame["Cumulative Withdrawals"].astype(float),
        ])
        figure.add_trace(
            go.Scatter(
                x=x,
                y=frame[median_col],
                mode="lines",
                name=f"{strategy} median",
                line={"color": color, "width": 3},
                customdata=custom,
                hovertemplate=(
                    "<b>%{x}</b><br>Balance / wealth: $%{y:,.2f}<br>Return: %{customdata[0]:+.2f}%"
                    "<br>Gross profit: $%{customdata[1]:+,.2f}<br>Withdrawal: $%{customdata[2]:,.2f}"
                    "<br>Cumulative withdrawals: $%{customdata[3]:,.2f}<extra>" + strategy + "</extra>"
                ),
            ),
            secondary_y=False,
        )
        if no_withdrawal:
            reference = strategies[strategy].get("no_withdrawal_chart", pd.DataFrame())
            if isinstance(reference, pd.DataFrame) and not reference.empty:
                reference_col = "Cumulative Wealth" if measure == "Cumulative Wealth" else "Median Ending Balance"
                figure.add_trace(
                    go.Scatter(
                        x=reference["Period"].astype(str),
                        y=reference[reference_col],
                        mode="lines",
                        name=f"{strategy} no withdrawal",
                        line={"color": "#94A3B8", "width": 2, "dash": "dash"},
                        hovertemplate="<b>%{x}</b><br>No-withdrawal balance: $%{y:,.2f}<extra></extra>",
                    ),
                    secondary_y=False,
                )
        if cumulative_withdrawals:
            figure.add_trace(
                go.Scatter(
                    x=x,
                    y=frame["Cumulative Withdrawals"],
                    mode="lines",
                    name=f"{strategy} cumulative withdrawals",
                    line={"color": color, "width": 1.6, "dash": "dot"},
                    hovertemplate="<b>%{x}</b><br>Cumulative withdrawals: $%{y:,.2f}<extra></extra>",
                ),
                secondary_y=True,
            )
        depletion_period = (strategies[strategy].get("summary") or {}).get("Median Depletion Period")
        if depletion_period:
            if str(depletion_period) not in set(x):
                depletion_period = str(depletion_period)[:4]
            match = frame.loc[frame["Period"].astype(str).eq(str(depletion_period))]
            if not match.empty:
                figure.add_trace(
                    go.Scatter(
                        x=[str(depletion_period)],
                        y=[float(match.iloc[0][median_col])],
                        mode="markers",
                        name=f"{strategy} depletion",
                        marker={"color": "#EF4444", "size": 11, "symbol": "x"},
                        hovertemplate="<b>%{x}</b><br>Median depletion point<extra></extra>",
                    ),
                    secondary_y=False,
                )
    figure.add_hline(
        y=float((result.get("inputs") or {}).get("starting_investment") or 0),
        line_dash="dot",
        line_color="#64748B",
        annotation_text="Starting investment",
    )
    period_count = max((len(strategies[name]["chart"]) for name in visible), default=1)
    figure.update_layout(
        height=540,
        margin={"l": 20, "r": 20, "t": 30, "b": 50},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(8,18,33,0.55)",
        font={"color": "#E2E8F0"},
        hovermode="x unified",
        legend={"orientation": "h", "y": 1.12, "x": 0},
        xaxis={"title": "Forecast period", "type": "category", "nticks": min(14, period_count)},
    )
    figure.update_yaxes(title_text=measure, tickprefix="$", separatethousands=True, secondary_y=False)
    figure.update_yaxes(title_text="Cumulative withdrawals", tickprefix="$", separatethousands=True, secondary_y=True)
    st.plotly_chart(figure, width="stretch", key="future_projection_performance_chart")


def _table_columns(frame: pd.DataFrame, monthly: bool, extended: bool) -> list[str]:
    if monthly:
        columns = [
            "Year", "Month", "Beginning Balance", "P10 Gross Profit", "Median Gross Profit", "P90 Gross Profit",
            "Median Monthly Return", "Requested Withdrawal", "Actual Withdrawal", "Withdrawal Shortfall",
            "Contribution", "Fees", "Median Net Change", "P10 Ending Balance", "Median Ending Balance",
            "P90 Ending Balance", "Cumulative Withdrawals", "Depletion Probability", "Status",
        ]
    else:
        columns = [
            "Year", "Beginning Balance", "P10 Gross Profit", "Median Gross Profit", "P90 Gross Profit",
            "Median Portfolio Return", "Requested Withdrawal", "Actual Withdrawal", "Withdrawal Shortfall",
            "Additional Contribution", "Fees", "Median Net Change", "P10 Ending Balance", "Median Ending Balance",
            "P90 Ending Balance", "Cumulative Withdrawals", "Total Wealth Profit", "Depletion Probability", "Status",
        ]
    if extended:
        insert_at = columns.index("P10 Ending Balance")
        columns.insert(insert_at, "P5 Ending Balance")
        columns.insert(columns.index("P90 Ending Balance") + 1, "P95 Ending Balance")
    return [column for column in columns if column in frame.columns]


def _style_projection_table(frame: pd.DataFrame):
    currency_columns = [
        column for column in frame.columns
        if any(token in column for token in ("Balance", "Profit", "Withdrawal", "Contribution", "Fees", "Net Change"))
    ]
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

    return frame.style.format(formats, na_rep="N/A").map(color_value, subset=[column for column in frame.columns if column in {"Median Gross Profit", "Median Net Change", "Total Wealth Profit", "Status"}])


def _render_strategy_table(strategy: str, payload: dict, monthly: bool, extended: bool) -> None:
    frame = payload.get("table", pd.DataFrame())
    if frame.empty:
        st.warning(f"No {strategy.lower()} projection rows are available.")
        return
    display = frame[_table_columns(frame, monthly, extended)].copy()
    st.dataframe(
        _style_projection_table(display),
        width="stretch",
        hide_index=True,
        height=min(720, 74 + len(display) * 34),
        key=f"fp_{strategy.lower().replace('-', '_')}_projection_table",
    )
    with st.expander(f"{strategy} holding-level detail", expanded=False):
        details = payload.get("holding_details", pd.DataFrame())
        if details.empty:
            st.info("Holding-level detail is unavailable.")
        else:
            st.dataframe(
                details,
                width="stretch",
                hide_index=True,
                height=min(650, 74 + len(details) * 30),
                key=f"fp_{strategy.lower().replace('-', '_')}_holding_details",
            )


def _render_results_tables(result: dict) -> None:
    strategies = result.get("strategies") or {}
    monthly = (result.get("metadata") or {}).get("output_frequency") == "Monthly"
    extended = bool((result.get("inputs") or {}).get("show_extended_range"))
    if len(strategies) == 2:
        rb_tab, nr_tab, side_tab = st.tabs(["Rebalanced", "Non-Rebalanced", "Side-by-Side"])
        with rb_tab:
            _render_strategy_table("Rebalanced", strategies["Rebalanced"], monthly, extended)
        with nr_tab:
            _render_strategy_table("Non-Rebalanced", strategies["Non-Rebalanced"], monthly, extended)
        with side_tab:
            comparison = result.get("comparison", pd.DataFrame())
            st.dataframe(comparison, width="stretch", hide_index=True, height=min(720, 74 + len(comparison) * 34))
    elif "Rebalanced" in strategies:
        only_tab, = st.tabs(["Rebalanced"])
        with only_tab:
            _render_strategy_table("Rebalanced", strategies["Rebalanced"], monthly, extended)
    elif "Non-Rebalanced" in strategies:
        only_tab, = st.tabs(["Non-Rebalanced"])
        with only_tab:
            _render_strategy_table("Non-Rebalanced", strategies["Non-Rebalanced"], monthly, extended)


def _render_exports(result: dict) -> None:
    seed = int((result.get("metadata") or {}).get("random_seed") or 0)
    columns = st.columns(3)
    try:
        csv_bytes = build_csv_export(result)
        excel_bytes = build_excel_export(result)
        pdf_bytes = build_pdf_export(result)
    except Exception:
        st.error("One or more exports could not be generated. Re-run the projection or verify the installed export dependencies.")
        return
    columns[0].download_button(
        "Download Excel",
        data=excel_bytes,
        file_name=f"MarketScope_Future_Projection_seed_{seed}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )
    columns[1].download_button(
        "Download CSV",
        data=csv_bytes,
        file_name=f"MarketScope_Future_Projection_seed_{seed}.csv",
        mime="text/csv",
        width="stretch",
    )
    columns[2].download_button(
        "Download PDF",
        data=pdf_bytes,
        file_name=f"MarketScope_Future_Projection_seed_{seed}.pdf",
        mime="application/pdf",
        width="stretch",
    )


def render_future_projection(
    market: pd.DataFrame,
    annual_year_columns: list[str] | tuple[str, ...],
    latest_completed_year: int,
    data_as_of: str,
    model_as_of: str,
    monthly_loader: Callable[[tuple[str, ...], tuple[str, ...]], dict] | None = None,
    logo_loader: Callable[[tuple[str, ...]], dict] | None = None,
    current_simulator_payload: dict | None = None,
) -> None:
    """Render the fully connected Future Projection workspace."""

    _initialize_state()
    pending = st.session_state.pop("future_projection_pending_payload", None)
    if pending:
        _apply_payload(pending)
        st.success("Loaded the selected MarketScope simulator portfolio. Review the assumptions, then run the projection.")

    st.markdown('<div class="fp-title">FUTURE PROJECTION</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="fp-disclaimer">{escape(DISCLAIMER)}</div>', unsafe_allow_html=True)
    meta_columns = st.columns(4)
    meta_columns[0].metric("Historical data as of", data_as_of or "Not available")
    meta_columns[1].metric("Model as of", model_as_of)
    meta_columns[2].metric("First forecast year", int(latest_completed_year) + 1)
    meta_columns[3].metric("Completed history through", int(latest_completed_year))

    lookup = market.copy()
    lookup["Symbol"] = lookup["Symbol"].astype(str).str.upper()
    lookup = lookup.drop_duplicates("Symbol", keep="last").set_index("Symbol", drop=False)
    all_symbols = sorted(lookup.index.tolist())

    with st.container(border=True):
        st.markdown("### Projection inputs")
        first_row = st.columns([1.3, 1.2, 1.25, 1.0])
        with first_row[0]:
            st.text_input(
                "Starting Investment",
                key="fp_starting_investment_text",
                help="Minimum $1,000. Commas and currency formatting are accepted.",
            )
        with first_row[1]:
            st.segmented_control(
                "Withdrawal Frequency",
                ["No Withdrawal", "Yearly", "Monthly"],
                key="fp_withdrawal_frequency",
            )
        with first_row[2]:
            frequency = st.session_state.fp_withdrawal_frequency
            if frequency == "Yearly":
                st.text_input("Annual Withdrawal", key="fp_annual_withdrawal_text")
                try:
                    annualized = parse_currency(st.session_state.fp_annual_withdrawal_text)
                    st.caption(f"Annualized withdrawal: {_money_text(annualized)}")
                except ProjectionValidationError:
                    st.caption("Enter a valid annual currency amount.")
            elif frequency == "Monthly":
                st.text_input("Monthly Withdrawal", key="fp_monthly_withdrawal_text")
                try:
                    annualized = parse_currency(st.session_state.fp_monthly_withdrawal_text) * 12.0
                    st.caption(f"Annualized withdrawal: {_money_text(annualized)}")
                except ProjectionValidationError:
                    st.caption("Enter a valid monthly currency amount.")
            else:
                st.text_input("Withdrawal Amount", value="$0", disabled=True, key="fp_no_withdrawal_display")
                st.caption("No portfolio withdrawals will be requested.")
        with first_row[3]:
            st.radio(
                "Withdrawal Timing",
                ["End of period", "Beginning of period"],
                key="fp_withdrawal_timing",
                disabled=st.session_state.fp_withdrawal_frequency == "No Withdrawal",
            )

        second_row = st.columns([1.0, 1.4, 1.2, 1.4])
        with second_row[0]:
            st.number_input("Future Years", min_value=1, max_value=50, step=1, key="fp_future_years")
            first_forecast = int(latest_completed_year) + 1
            st.caption(f"Forecast range: {first_forecast}-{first_forecast + int(st.session_state.fp_future_years) - 1}")
        with second_row[1]:
            st.segmented_control("Projection Strategy", ["Rebalanced", "Non-Rebalanced", "Both"], key="fp_strategy")
        with second_row[2]:
            st.selectbox(
                "Rebalancing Frequency",
                ["Yearly", "Quarterly", "Monthly"],
                key="fp_rebalancing_frequency",
                disabled=st.session_state.fp_strategy == "Non-Rebalanced",
            )
        with second_row[3]:
            quality = st.selectbox(
                "Scenario Quality",
                ["Standard", "Advanced", "High Precision"],
                key="fp_scenario_quality",
                format_func=lambda value: f"{value} - {model_defaults()['simulation_counts'][value]:,} simulations",
            )
            if quality == "High Precision":
                st.warning("High Precision runs 50,000 simulations and may take longer.")

        st.markdown("#### Portfolio holdings")
        holding_columns = st.columns(4)
        for idx, column in enumerate(holding_columns, start=1):
            key = f"fp_holding_{idx}"
            current = str(st.session_state.get(key) or "")
            other = {
                str(st.session_state.get(f"fp_holding_{other_idx}") or "")
                for other_idx in range(1, 5) if other_idx != idx
            }
            options = [""] + [symbol for symbol in all_symbols if symbol not in other or symbol == current]
            if current and current not in options:
                st.session_state[key] = ""
            with column:
                st.selectbox(
                    f"Stock/ETF {idx}",
                    options=options,
                    key=key,
                    format_func=lambda symbol, _lookup=lookup: _holding_option_label(symbol, _lookup),
                    placeholder="Search ticker or name...",
                )
        holdings = [str(st.session_state.get(f"fp_holding_{idx}") or "") for idx in range(1, 5)]
        _render_selected_holding_cards(holdings, lookup, logo_loader)

        action_columns = st.columns([1, 1.4, 3])
        action_columns[0].button(
            "Clear Portfolio",
            width="stretch",
            on_click=_clear_portfolio,
        )
        can_use_current = bool(current_simulator_payload and len(current_simulator_payload.get("holdings") or []) == 4)
        action_columns[1].button(
            "Use Current Simulator Portfolio",
            disabled=not can_use_current,
            width="stretch",
            help="Loads the current historical simulator's four holdings, amount, withdrawals, and allocation.",
            on_click=_apply_payload,
            args=(current_simulator_payload or {},),
        )

        st.segmented_control("Allocation", ["Equal Split", "Custom Allocation"], key="fp_allocation_mode")
        if st.session_state.fp_allocation_mode == "Equal Split":
            for idx in range(1, 5):
                st.session_state[f"fp_allocation_{idx}"] = 25.0
            st.caption("Equal Split assigns exactly 25.00% to each of the four holdings. Live total: 100.00%")
        else:
            allocation_columns = st.columns(4)
            for idx, column in enumerate(allocation_columns, start=1):
                symbol = holdings[idx - 1] or f"Holding {idx}"
                with column:
                    st.number_input(
                        f"{symbol} allocation %",
                        min_value=0.0,
                        max_value=100.0,
                        step=0.25,
                        format="%.2f",
                        key=f"fp_allocation_{idx}",
                    )
            allocation_total = sum(float(st.session_state.get(f"fp_allocation_{idx}") or 0.0) for idx in range(1, 5))
            tone = "fp-total-valid" if abs(allocation_total - 100.0) <= 1e-8 else "fp-total-invalid"
            st.markdown(f'<div class="fp-allocation-total {tone}">Live allocation total: {allocation_total:.2f}%</div>', unsafe_allow_html=True)

        with st.expander("Advanced Settings", expanded=False):
            advanced = st.columns(3)
            with advanced[0]:
                st.toggle("Inflation-adjust withdrawals", key="fp_inflation_adjust")
                st.number_input(
                    "Annual withdrawal inflation rate (%)",
                    min_value=-99.0,
                    max_value=25.0,
                    step=0.1,
                    format="%.2f",
                    key="fp_withdrawal_inflation_pct",
                    disabled=not st.session_state.fp_inflation_adjust,
                )
                st.number_input(
                    "Annual management fee (%)",
                    min_value=0.0,
                    max_value=99.0,
                    step=0.05,
                    format="%.3f",
                    key="fp_management_fee_pct",
                )
            with advanced[1]:
                contribution_label = "Additional monthly contribution" if st.session_state.fp_withdrawal_frequency == "Monthly" else "Additional annual contribution"
                st.text_input(contribution_label, key="fp_contribution_text")
                st.number_input("Random seed", min_value=0, max_value=2_147_483_647, step=1, key="fp_random_seed")
                st.toggle("Include no-withdrawal comparison", key="fp_include_no_withdrawal")
                st.toggle("Show P5/P95 extended range", key="fp_show_extended")
            with advanced[2]:
                st.date_input("Capital-market assumption date", key="fp_cma_date")
                cma = capital_market_assumptions()["broad_market_annual_geometric_return"]
                st.markdown(
                    "**Expected-return model details**  \n"
                    f"Broad-market anchor: {float(cma['value']) * 100:.2f}%  \n"
                    f"Source: {cma['source']}  \n"
                    f"As of: {cma['as_of_date']}  \n"
                    f"Last updated: {cma['last_updated_date']}  \n"
                    "70% capital-market shrinkage; 20% security excess-return signal; 10% sector/ETF-category signal. "
                    "Residual covariance is shrunk 55%; Bear, Normal, and Bull regimes use Markov transitions and Student-t(6) shocks."
                )

    projection_inputs, parse_errors = _build_inputs(int(latest_completed_year))
    validation_errors, validation_warnings = validate_projection_inputs(projection_inputs, market)
    all_errors = [*parse_errors, *validation_errors]
    for warning in validation_warnings:
        st.warning(warning)
    if all_errors:
        st.error("Projection cannot run yet: " + " ".join(dict.fromkeys(all_errors)))

    run_columns = st.columns([1.5, 1, 4])
    run_clicked = run_columns[0].button(
        "Run Projection",
        type="primary",
        disabled=bool(all_errors) or bool(st.session_state.fp_running),
        width="stretch",
    )
    run_columns[1].button(
        "Reset",
        disabled=bool(st.session_state.fp_running),
        width="stretch",
        on_click=_reset_projection,
    )
    if run_clicked:
        st.session_state.fp_running = True
        monthly_payload = {}
        needs_monthly = (
            projection_inputs["withdrawal_frequency"] == "Monthly"
            or (
                projection_inputs["strategy"] in {"Rebalanced", "Both"}
                and projection_inputs["rebalancing_frequency"] in {"Quarterly", "Monthly"}
            )
        )
        if needs_monthly and monthly_loader is not None:
            with st.spinner("Loading actual monthly return history and identifying explicit fallback periods..."):
                try:
                    monthly_payload = monthly_loader(tuple(projection_inputs["holdings"]), tuple(annual_year_columns)) or {}
                except Exception:
                    monthly_payload = {"unavailable": True, "returns": {}, "reason": "Actual monthly history loader did not complete."}
        key = projection_cache_key(projection_inputs, market, annual_year_columns, monthly_payload, data_as_of)
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
                    future = executor.submit(
                        run_future_projection,
                        market,
                        projection_inputs,
                        annual_year_columns,
                        monthly_payload,
                        data_as_of,
                        model_as_of,
                        report_progress,
                    )
                    while not future.done():
                        latest = None
                        while True:
                            try:
                                latest = progress_events.get_nowait()
                            except queue.Empty:
                                break
                        if latest:
                            completed, total, label = latest
                            progress_bar.progress(
                                min(0.99, completed / max(1, total)),
                                text=f"{label} - simulations completed: {completed:,} / {total:,}",
                            )
                        time.sleep(0.04)
                    result = future.result()
                progress_bar.progress(1.0, text=f"Simulations completed: {projection_inputs['simulation_count']:,} / {projection_inputs['simulation_count']:,}")
                cache[key] = result
                while len(cache) > 5:
                    cache.pop(next(iter(cache)))
                st.session_state.fp_result_cache = cache
                st.session_state.fp_result = result
                st.success(f"Projection complete - {projection_inputs['simulation_count']:,} deterministic Monte Carlo simulations.")
            except ProjectionValidationError as exc:
                st.error(str(exc))
            except Exception as exc:
                print(f"Future Projection internal error: {type(exc).__name__}: {exc}")
                st.error("The projection could not be completed. Verify the selected holdings and historical data, then try again.")
            finally:
                st.session_state.fp_running = False

    result = st.session_state.get("fp_result")
    if not result:
        st.info("Complete all four holdings and select Run Projection to generate probabilistic results.")
        return
    metadata = result.get("metadata") or {}
    st.markdown("### Projection results")
    st.caption(
        f"Data as of {metadata.get('data_as_of')} - model as of {metadata.get('model_as_of')} - "
        f"{int(metadata.get('simulation_count') or 0):,} simulations - fixed seed {metadata.get('random_seed')} - "
        f"{metadata.get('base_frequency')} model / {metadata.get('output_frequency')} results"
    )
    for warning in result.get("warnings") or []:
        st.warning(warning)
    _render_summary(result)
    st.markdown("### Performance projection")
    _render_chart(result)
    st.markdown("### Detailed projection tables")
    _render_results_tables(result)
    with st.expander("Model assumptions, diagnostics, sources, and limitations", expanded=False):
        st.markdown("#### Model assumptions")
        _assumption_display = result.get("model_assumptions", pd.DataFrame()).copy()
        if "Value" in _assumption_display.columns:
            _assumption_display["Value"] = _assumption_display["Value"].map(str)
        st.dataframe(_assumption_display, width="stretch", hide_index=True)
        st.markdown("#### Stock/ETF assumptions and history quality")
        st.dataframe(result.get("holding_assumptions", pd.DataFrame()), width="stretch", hide_index=True)
        st.markdown("#### Diagnostics")
        st.json(result.get("diagnostics") or {})
        st.markdown("#### Sources and limitations")
        for limitation in result.get("limitations") or []:
            st.markdown(f"- {limitation}")
    st.markdown("### Export")
    _render_exports(result)
