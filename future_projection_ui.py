"""MarketScope Future Projection UI enhancements.

v5.10.3 keeps the v5.10.1 UI and v5.10.2 summary enhancements intact, then
adds P25/P50/P75 annual profit amounts and annual return percentages to the
year-by-year results table and a dedicated central-percentile graph.
"""

from __future__ import annotations

import numbers

import numpy as np
import pandas as pd
import streamlit as st

import future_projection_ui_legacy as _legacy

# Preserve the complete v5.10.1 UI surface.
for _name in dir(_legacy):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_legacy, _name)

_original_summary_metrics = _legacy._summary_metrics
_original_format_summary_value = _legacy._format_summary_value
_original_render_chart = _legacy._render_chart


def _summary_metrics(summary: dict, show_extended: bool, include_no_withdrawal: bool) -> list[str]:
    metrics = list(_original_summary_metrics(summary, show_extended, include_no_withdrawal))

    # Keep the v5.10.2 central probability range prominent while retaining all
    # existing P10/P90 and optional P5/P95 cards.
    central = [
        "P25 Ending Balance",
        "P50 Ending Balance",
        "P75 Ending Balance",
        "Profit %",
    ]
    insert_at = (
        metrics.index("Median Ending Balance")
        if "Median Ending Balance" in metrics
        else min(4, len(metrics))
    )
    for metric in reversed(central):
        if metric not in metrics:
            metrics.insert(insert_at, metric)
    return metrics


def _format_summary_value(metric: str, value) -> str:
    if isinstance(value, numbers.Number) and (
        metric.endswith("Profit %") or metric == "Profit %"
    ):
        return f"{float(value):,.2f}%"
    return _original_format_summary_value(metric, value)


def _table_columns(frame: pd.DataFrame, monthly: bool, extended: bool) -> list[str]:
    """Put P25/P50/P75 profit and return percentiles beside the existing tails."""

    if monthly:
        columns = [
            "Year",
            "Month",
            "Beginning Balance",
            "P10 Gross Profit",
            "P25 Gross Profit",
            "P50 Gross Profit",
            "P75 Gross Profit",
            "P90 Gross Profit",
            "P25 Monthly Return",
            "P50 Monthly Return",
            "P75 Monthly Return",
            "Requested Withdrawal",
            "Actual Withdrawal",
            "Withdrawal Shortfall",
            "Contribution",
            "Fees",
            "Median Net Change",
            "P10 Ending Balance",
            "P25 Ending Balance",
            "P50 Ending Balance",
            "P75 Ending Balance",
            "P90 Ending Balance",
            "Cumulative Withdrawals",
            "Depletion Probability",
            "Status",
        ]
    else:
        columns = [
            "Year",
            "Beginning Balance",
            "P10 Gross Profit",
            "P25 Gross Profit",
            "P50 Gross Profit",
            "P75 Gross Profit",
            "P90 Gross Profit",
            "P25 Annual Return",
            "P50 Annual Return",
            "P75 Annual Return",
            "Requested Withdrawal",
            "Actual Withdrawal",
            "Withdrawal Shortfall",
            "Additional Contribution",
            "Fees",
            "Median Net Change",
            "P10 Ending Balance",
            "P25 Ending Balance",
            "P50 Ending Balance",
            "P75 Ending Balance",
            "P90 Ending Balance",
            "Cumulative Withdrawals",
            "Total Wealth Profit",
            "Depletion Probability",
            "Status",
        ]

    if extended:
        if "P10 Ending Balance" in columns:
            insert_at = columns.index("P10 Ending Balance")
            columns.insert(insert_at, "P5 Ending Balance")
        if "P90 Ending Balance" in columns:
            columns.insert(columns.index("P90 Ending Balance") + 1, "P95 Ending Balance")

    # Compatibility fallback for an in-memory result generated just before a
    # deployment/reload. Fresh v5.10.3 runs use the explicit P50 names.
    if "P50 Gross Profit" not in frame.columns and "Median Gross Profit" in frame.columns:
        columns = [
            "Median Gross Profit" if c == "P50 Gross Profit" else c
            for c in columns
        ]
    if monthly:
        if "P50 Monthly Return" not in frame.columns and "Median Monthly Return" in frame.columns:
            columns = [
                "Median Monthly Return" if c == "P50 Monthly Return" else c
                for c in columns
            ]
    else:
        if "P50 Annual Return" not in frame.columns and "Median Portfolio Return" in frame.columns:
            columns = [
                "Median Portfolio Return" if c == "P50 Annual Return" else c
                for c in columns
            ]

    return [column for column in columns if column in frame.columns]


def _style_projection_table(frame: pd.DataFrame):
    currency_columns = [
        column
        for column in frame.columns
        if any(
            token in column
            for token in (
                "Balance",
                "Profit",
                "Withdrawal",
                "Contribution",
                "Fees",
                "Net Change",
            )
        )
        and "%" not in column
        and "Return" not in column
    ]
    percent_columns = [
        column
        for column in frame.columns
        if "Return" in column or "Probability" in column or column.endswith("Profit %")
    ]

    formats = {column: "${:,.2f}" for column in currency_columns}
    formats.update(
        {
            column: (
                "{:+,.2f}%"
                if ("Return" in column or column.endswith("Profit %"))
                else "{:,.2f}%"
            )
            for column in percent_columns
        }
    )

    def color_value(value):
        if isinstance(value, str):
            if "Depleted" in value:
                return "color:#F87171;font-weight:700"
            if "Partial" in value:
                return "color:#FBBF24;font-weight:700"
            if value == "Active":
                return "color:#34D399;font-weight:700"
        if isinstance(value, (int, float, np.number)):
            return (
                "color:#34D399"
                if float(value) > 0
                else ("color:#F87171" if float(value) < 0 else "")
            )
        return ""

    emphasis = [
        column
        for column in frame.columns
        if (
            "Gross Profit" in column
            or "Annual Return" in column
            or "Monthly Return" in column
            or column in {"Median Net Change", "Total Wealth Profit", "Status"}
        )
    ]

    return frame.style.format(formats, na_rep="N/A").map(
        color_value,
        subset=emphasis,
    )


def _render_central_percentile_chart(result: dict) -> None:
    """Render P25/P50/P75 annual profit or return without disturbing the main chart."""

    try:
        import plotly.graph_objects as go
    except Exception:
        st.error(
            "The annual percentile chart dependency is unavailable. "
            "Install the packages in requirements.txt and restart MarketScope."
        )
        return

    strategies = result.get("strategies") or {}
    if not strategies:
        return

    metadata = result.get("metadata") or {}
    monthly_output = metadata.get("output_frequency") == "Monthly"

    st.markdown("#### Annual P25 / P50 / P75 Projection")
    if monthly_output:
        st.caption(
            "This projection is currently displaying monthly output. "
            "The P25/P50/P75 values remain available in the monthly table; "
            "run a yearly-output projection to view the annual percentile graph."
        )
        return

    names = list(strategies)
    selected = st.session_state.get("fp_chart_visible_strategies", names)
    if isinstance(selected, str):
        selected = [selected]
    visible = [name for name in selected if name in strategies] or names

    measure = st.segmented_control(
        "Annual percentile graph",
        ["Annual Profit", "Annual Return %"],
        default="Annual Profit",
        key="fp_annual_percentile_chart_measure",
    )

    figure = go.Figure()
    base_colors = {
        "Rebalanced": "#2F80ED",
        "Non-Rebalanced": "#F59E0B",
    }
    dash_by_percentile = {
        "P25": "dash",
        "P50": "solid",
        "P75": "dot",
    }
    width_by_percentile = {
        "P25": 2,
        "P50": 3,
        "P75": 2,
    }

    if measure == "Annual Return %":
        data_keys = {
            "P25": "P25 Annual Return",
            "P50": "P50 Annual Return",
            "P75": "P75 Annual Return",
        }
        y_title = "Annual return"
        hover_value = "%{y:+.2f}%"
        tick_suffix = "%"
        tick_prefix = ""
    else:
        data_keys = {
            "P25": "P25 Gross Profit",
            "P50": "P50 Gross Profit",
            "P75": "P75 Gross Profit",
        }
        y_title = "Annual gross profit"
        hover_value = "$%{y:+,.2f}"
        tick_suffix = ""
        tick_prefix = "$"

    plotted = 0
    for strategy in visible:
        frame = strategies[strategy].get("chart", pd.DataFrame())
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            continue

        x = frame["Period"].astype(str)
        color = base_colors.get(strategy, "#94A3B8")

        for percentile, key in data_keys.items():
            if key not in frame.columns:
                continue

            figure.add_trace(
                go.Scatter(
                    x=x,
                    y=pd.to_numeric(frame[key], errors="coerce"),
                    mode="lines+markers",
                    name=f"{strategy} {percentile}",
                    line={
                        "color": color,
                        "width": width_by_percentile[percentile],
                        "dash": dash_by_percentile[percentile],
                    },
                    marker={"size": 5 if percentile == "P50" else 4},
                    hovertemplate=(
                        f"<b>%{{x}}</b><br>{percentile} {y_title}: "
                        + hover_value
                        + f"<extra>{strategy}</extra>"
                    ),
                )
            )
            plotted += 1

    if not plotted:
        st.info(
            "Run the projection again after this update so the new annual "
            "P25/P50/P75 values are generated."
        )
        return

    figure.update_layout(
        height=430,
        margin={"l": 20, "r": 20, "t": 25, "b": 50},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(8,18,33,0.55)",
        font={"color": "#E2E8F0"},
        hovermode="x unified",
        legend={"orientation": "h", "y": 1.16, "x": 0},
        xaxis={"title": "Forecast year", "type": "category"},
        yaxis={
            "title": y_title,
            "tickprefix": tick_prefix,
            "ticksuffix": tick_suffix,
            "separatethousands": True,
        },
    )

    if measure == "Annual Return %":
        figure.add_hline(y=0, line_dash="dot", line_color="#64748B")

    st.plotly_chart(
        figure,
        width="stretch",
        key="future_projection_annual_percentile_chart",
    )
    st.caption(
        "P25 means 25% of modeled outcomes are at or below that line; "
        "P50 is the median; P75 means 75% are at or below that line."
    )


def _render_chart(result: dict) -> None:
    # Preserve the existing balance / cumulative-wealth graph exactly.
    _original_render_chart(result)

    # Add the requested annual P25/P50/P75 profit and return visualization.
    _render_central_percentile_chart(result)


# Patch helpers that the original v5.10.1 render function resolves at runtime.
_legacy._summary_metrics = _summary_metrics
_legacy._format_summary_value = _format_summary_value
_legacy._table_columns = _table_columns
_legacy._style_projection_table = _style_projection_table
_legacy._render_chart = _render_chart

# The original render function now resolves the patched helpers above.
render_future_projection = _legacy.render_future_projection
