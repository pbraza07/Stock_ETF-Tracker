"""Dynamic ranking workspaces with cached computation and report generation."""

import hashlib
import json
import logging
from datetime import datetime, timezone
import pandas as pd
import numpy as np
import streamlit as st
from top12_rankings import build_top12_rankings, walk_forward_rankings, PERCENTILES
from top12_history import load_ledger, current_table, record_run, persist_ledger
from top12_exports import DISCLOSURES, LIMITATION
from runtime_performance import ranking_exports
from future_projection import run_future_projection
from top12_jobs import EXECUTOR, SAVE_EXECUTOR, calculate_rankings, save_histories


def request_ranking(kind):
    # Persist intent in the callback itself. A tab/full-app rerun can consume
    # Streamlit's one-run button pulse before this workspace renders again.
    st.session_state.t12_pending_request = kind
    st.session_state.t12_input_view = kind
    # The callback runs before the app recreates its lazy top-level tabs.
    if st.session_state.get("workspace_navigation") != "Favorite Picks":
        st.session_state.workspace_navigation = "Favorite Picks"


def consume_completed_job():
    job = st.session_state.get("t12_job")
    if job and job["future"].done():
        st.session_state.pop("t12_job")
        try:
            payload = job["future"].result()
            st.session_state.t12_result = payload["result"]
            st.session_state.t12_histories = payload["histories"]
            st.session_state.t12_fingerprint = job["fingerprint"]
            st.session_state.t12_portfolios = {}
            st.session_state.t12_save_messages = []
            st.session_state.t12_save_job = SAVE_EXECUTOR.submit(
                save_histories, payload["histories"]
            )
        except Exception as exc:
            logging.getLogger(__name__).exception("Top 5 per Sector calculation failed")
            st.session_state.t12_error = (
                str(exc)
                if isinstance(exc, ValueError)
                else "Top 5 per Sector calculation failed. Your previous result is retained. Retry the button; technical details were recorded in the server log."
            )
    saved = st.session_state.get("t12_save_job")
    if saved and saved.done():
        st.session_state.pop("t12_save_job")
        try:
            st.session_state.t12_save_messages = saved.result()
        except Exception:
            st.session_state.t12_save_messages = [
                (False, "History save failed; ranking results remain available.")
            ]
        cached_ledger.clear()


@st.cache_data(ttl=60, max_entries=4, show_spinner=False)
def cached_ledger(kind):
    return load_ledger(kind)



RECESSION_SAVED_COLUMNS = [
    "Rank", "Symbol", "Name", "Sector", "Price",
    "Recession Score",
    "Defense Score", "Drawdown Score", "Recovery Score", "Bear Model Score",
    "Consistency Score", "Current Strength Score", "Profitability Score",
    "Risk Penalty", "Recession Additional Penalty",
    "Worst Stress Return %", "Mean Stress Return %",
    "Stress Market Excess %", "Stress Sector Excess %",
    "Stress Drawdown %", "Stress Events", "Stress Evidence Basis",
    "Maximum Drawdown %", "Recovery Periods", "Recovery Basis",
    "Bear P10 Future Return %", "Bear P25 Future Return %",
    "Bear P50 Future Return %", "Bear P75 Future Return %", "Bear P90 Future Return %",
    "Positive Years %", "Historical CAGR %",
    "Data Quality Score", "Data Confidence", "Why Selected",
]

MAX_PROFIT_SAVED_COLUMNS = [
    "Rank", "Symbol", "Name", "Sector", "Price",
    "Max Profit Score",
    "Historical Performance Score", "Recent Performance Score",
    "Future P50 Score", "Future P75 Score", "Fundamentals Score",
    "Consistency Score", "Relative Strength Score", "Downside Quality Score",
    "Risk Penalty",
    "3Y CAGR %", "5Y CAGR %", "10Y CAGR %",
    "P10 Future Return %", "P25 Future Return %",
    "P50 Future Return %", "P75 Future Return %", "P90 Future Return %",
    "Positive Years %", "Maximum Drawdown %",
    "Best Historical Year %", "Worst Historical Year %",
    "P50 Projected Profit", "P75 Projected Profit",
    "Data Quality Score", "Data Confidence", "Why Selected",
]

PERSISTED_TABLE_RENAMES = {
    "Symbol": "Ticker",
    "Name": "Company",
    "Price": "Current Price",
    "Recession Score": "Final Recession Score",
    "Defense Score": "Defense Score (30%)",
    "Drawdown Score": "Drawdown Score (20%)",
    "Recovery Score": "Recovery Score (15%)",
    "Bear Model Score": "Bear Model Score (15%)",
    "Consistency Score": "Consistency Score",
    "Current Strength Score": "Current Strength Score (5%)",
    "Profitability Score": "Profitability Score (5%)",
    "Recession Additional Penalty": "Recession Penalty",
    "Maximum Drawdown %": "Max Drawdown %",
    "Recovery Periods": "Recovery Time",
    "Bear P10 Future Return %": "Bear P10 %",
    "Bear P25 Future Return %": "Bear P25 %",
    "Bear P50 Future Return %": "Bear P50 %",
    "Bear P75 Future Return %": "Bear P75 %",
    "Bear P90 Future Return %": "Bear P90 %",
    "Max Profit Score": "Final Max-Profit Score",
    "Historical Performance Score": "Historical Performance (25%)",
    "Recent Performance Score": "Recent Performance (15%)",
    "Future P50 Score": "Future P50 Score (20%)",
    "Future P75 Score": "Future P75 Score (15%)",
    "Fundamentals Score": "Fundamentals Score (10%)",
    "Relative Strength Score": "Relative Strength Score (5%)",
    "Downside Quality Score": "Downside Quality Score (5%)",
    "Positive Years %": "Positive Years %",
}


def _saved_columns(kind):
    return RECESSION_SAVED_COLUMNS if kind == "Recession" else MAX_PROFIT_SAVED_COLUMNS


def _primary_factor_columns(kind):
    if kind == "Recession":
        return [
            "Rank", "Symbol", "Name", "Sector", "Price",
            "Recession Score",
            "Defense Score", "Drawdown Score", "Recovery Score", "Bear Model Score",
            "Consistency Score", "Current Strength Score", "Profitability Score",
            "Risk Penalty", "Recession Additional Penalty",
            "Worst Stress Return %", "Maximum Drawdown %",
            "Recovery Periods", "Recovery Basis",
            "Bear P10 Future Return %", "Bear P25 Future Return %",
            "Positive Years %", "Historical CAGR %",
            "Data Confidence", "Why Selected",
        ]
    return [
        "Rank", "Symbol", "Name", "Sector", "Price",
        "Max Profit Score",
        "Historical Performance Score", "Recent Performance Score",
        "Future P50 Score", "Future P75 Score", "Fundamentals Score",
        "Consistency Score", "Relative Strength Score", "Downside Quality Score",
        "Risk Penalty",
        "3Y CAGR %", "5Y CAGR %", "10Y CAGR %",
        "P10 Future Return %", "P25 Future Return %",
        "P50 Future Return %", "P75 Future Return %",
        "Positive Years %", "Maximum Drawdown %",
        "Data Confidence", "Why Selected",
    ]


def _legacy_factor_run(table, kind):
    required = (
        {"Defense Score", "Drawdown Score", "Recovery Score", "Bear Model Score"}
        if kind == "Recession"
        else {
            "Historical Performance Score", "Recent Performance Score",
            "Future P50 Score", "Future P75 Score", "Fundamentals Score"
        }
    )
    return not required.issubset(set(table.columns))


def _latest_persisted_run(kind):
    """Return the newest complete 12-row run from the tracked GitHub history ledger."""
    ledger = cached_ledger(kind)
    score = kind + " Score"
    required = {"Rank", "Symbol", "Sector", score}
    for run in reversed((ledger or {}).get("runs") or []):
        holdings = run.get("Holdings")
        if not isinstance(holdings, list) or not holdings or (run.get("Metadata") or {}).get("Selection Policy") != "Top 5 per sector":
            continue
        table = pd.DataFrame(holdings)
        if required.issubset(table.columns):
            table = table.sort_values("Rank", kind="stable").reset_index(drop=True)
            return ledger, run, table
    return ledger, None, pd.DataFrame()


def _persisted_display_table(table, kind, market):
    """Preserve saved ranking evidence and enrich only missing name/price fields."""
    display = table.copy()

    if isinstance(market, pd.DataFrame) and not market.empty and "Symbol" in market.columns:
        lookup = market.drop_duplicates("Symbol", keep="last").set_index("Symbol")
        for column in ("Name", "Price"):
            if column not in lookup.columns:
                continue
            mapped = display["Symbol"].map(lookup[column])
            if column not in display.columns:
                display[column] = mapped
            else:
                display[column] = display[column].where(display[column].notna(), mapped)

    ordered = [column for column in _primary_factor_columns(kind) if column in display.columns]
    display = display[ordered].rename(columns=PERSISTED_TABLE_RENAMES)
    if "Consistency Score" in display.columns:
        display = display.rename(
            columns={
                "Consistency Score": (
                    "Consistency Score (10%)"
                    if kind == "Recession"
                    else "Consistency Score (5%)"
                )
            }
        )
    return display


def _ranking_factor_config(display):
    config = {
        "Rank": st.column_config.NumberColumn("Rank", pinned=True, format="%d"),
        "Ticker": st.column_config.TextColumn("Ticker", pinned=True),
    }
    if "Current Price" in display.columns:
        config["Current Price"] = st.column_config.NumberColumn(format="$%.2f")

    percent_columns = [
        column for column in display.columns
        if "%" in column and column not in {
            "Defense Score (30%)", "Drawdown Score (20%)", "Recovery Score (15%)",
            "Bear Model Score (15%)", "Current Strength Score (5%)",
            "Profitability Score (5%)", "Historical Performance (25%)",
            "Recent Performance (15%)", "Future P50 Score (20%)",
            "Future P75 Score (15%)", "Fundamentals Score (10%)",
            "Relative Strength Score (5%)", "Downside Quality Score (5%)",
            "Consistency Score (10%)", "Consistency Score (5%)",
        }
    ]
    for column in percent_columns:
        config[column] = st.column_config.NumberColumn(format="%.2f%%")

    for column in display.columns:
        if "Score" in column or column in {
            "Historical Performance (25%)", "Recent Performance (15%)",
            "Final Max-Profit Score", "Risk Penalty", "Recession Penalty",
        }:
            config[column] = st.column_config.NumberColumn(format="%.2f")

    return config


def render_persisted_ranked_table(kind, market):
    """Render saved ranking plus the factor/evidence columns that produced its score."""
    ledger, run, table = _latest_persisted_run(kind)
    if run is None or table.empty:
        st.info(
            f"No complete saved {kind} Top 5 per Sector result is available yet. Use Advanced recalculation below to create one."
        )
        return ledger, pd.DataFrame()

    st.subheader(
        "Top 5 per Sector Recession-Resilient Stocks"
        if kind == "Recession"
        else "Top 5 per Sector Max-Profit High-Performance Stocks"
    )
    st.warning(DISCLOSURES[kind])
    st.caption(f"{len(table)} selected stocks across {table.Sector.nunique()} sectors; up to five per sector.")

    metadata = run.get("Metadata") or {}
    generated = metadata.get("Ranking Generated") or run.get("Timestamp") or "Unavailable"
    model = metadata.get("Model Version") or "Unavailable"
    market_through = metadata.get("Market Data Through") or "Unavailable"
    st.caption(
        f"Saved ranking result • Generated {generated} • Model {model} • Market data through {market_through}"
    )

    if _legacy_factor_run(table, kind):
        st.warning(
            "This saved ranking predates the ranking-factor audit schema, so its JSON only contains rank, ticker, "
            "sector and final score. Run Advanced recalculation once to save the complete factor evidence used for "
            "future table displays. The existing ranking is not altered merely by opening this table."
        )

    display = _persisted_display_table(table, kind, market)
    st.dataframe(
        display,
        hide_index=True,
        column_config=_ranking_factor_config(display),
        width="stretch",
        key="top12_saved_" + kind.lower().replace(" ", "_") + "_table",
    )
    st.caption(
        "Factor-score columns are 0-100 comparative scores used by the ranking formula. Raw evidence columns show "
        "the actual historical/model inputs behind those factor scores. Final score is the weighted factor total "
        "after applicable penalties. Opening the table does not recalculate or reorder the saved ranking."
    )

    with st.expander("Saved ranking details"):
        if metadata:
            details = pd.DataFrame(
                [{"Field": key, "Value": value} for key, value in metadata.items()]
            )
            st.dataframe(details, hide_index=True, width="stretch")
        events = pd.DataFrame((ledger or {}).get("events", []))
        if not events.empty:
            st.markdown("**Change history**")
            st.dataframe(events, hide_index=True, width="stretch")
    return ledger, table


@st.cache_data(ttl=3600, max_entries=4, show_spinner=False)
def cached_rankings(market, years, monthly, live, simulations, previous, threshold):
    return build_top12_rankings(
        market,
        years,
        monthly,
        live,
        simulations,
        previous=previous,
        threshold=threshold,
    )


@st.cache_data(ttl=3600, max_entries=2, show_spinner=False)
def cached_backtest(market, years):
    return walk_forward_rankings(market, years)


def portfolio_inputs(table, kind, allocation, investment, years):
    weights = (
        np.ones(len(table))
        if allocation == "Equal Weight"
        else table[kind + " Score"].to_numpy(float)
    )
    weights = (
        weights / weights.sum() * 100
        if weights.sum() > 0
        else np.ones(len(table)) / len(table) * 100
    )
    weights[-1] = 100.0 - float(weights[:-1].sum())
    return {
        "starting_investment": investment,
        "holdings": table.Symbol.tolist(),
        "allocations": dict(zip(table.Symbol, weights)),
        "allocation_mode": "Custom Allocation",
        "strategy": "Both",
        "withdrawal_frequency": "No Withdrawal",
        "future_years": years,
        "simulation_count": 5000,
        "random_seed": 42,
        "forecast_start_year": datetime.now(timezone.utc).year,
        "projection_profile": "STRESS TEST" if kind == "Recession" else "AUTO",
    }


def render_top12_rankings(market, years, data_as_of, monthly_loader, live_loader):
    """Open the selected tracked JSON ranking immediately; recalculation is optional."""
    consume_completed_job()
    st.markdown("### Dynamic sector stock rankings")
    st.caption("Five highest-scoring eligible stocks per sector. Existing model eligibility and scoring apply; relative rank is not a guarantee of resilience or profit.")
    columns = st.columns(2)
    columns[0].button(
        "🛡️ Top 5 per Sector Recession-Resilient Stocks",
        key="t12_recession",
        on_click=request_ranking,
        args=("Recession",),
        use_container_width=True,
    )
    columns[1].button(
        "🚀 Top 5 per Sector Max-Profit High-Performance Stocks",
        key="t12_profit",
        on_click=request_ranking,
        args=("Max Profit",),
        use_container_width=True,
    )

    requested = st.session_state.pop("t12_pending_request", None)
    if requested:
        st.session_state.t12_active_kind = requested
        st.session_state.t12_input_view = requested
        st.session_state.t12_show_full_analysis = False
        st.session_state.pop("t12_error", None)

    kind = st.session_state.get("t12_active_kind") or st.session_state.get(
        "t12_input_view"
    )
    if kind not in ("Recession", "Max Profit"):
        st.info(
            "Select either Top 5 per Sector button. Its saved sector-leader result will open below as a table."
        )
        return

    history, saved_table = render_persisted_ranked_table(kind, market)

    fingerprint = hashlib.sha256(
        pd.util.hash_pandas_object(market, index=True).values.tobytes()
        + str(data_as_of).encode()
    ).hexdigest()

    with st.expander("Advanced recalculation and full analysis"):
        st.caption(
            "The main table above comes directly from the saved ranking history. Recalculate only when you intentionally want MarketScope to rebuild both Top 5 per Sector rankings from current app data."
        )
        threshold = st.number_input(
            "Replacement threshold (ranking points)",
            0.0,
            10.0,
            1.0,
            0.25,
            key="t12_input_threshold",
        )
        recalculate = st.button(
            "Recalculate Top 5 per Sector rankings",
            key="t12_recalculate",
            use_container_width=True,
        )
        if recalculate or (requested and saved_table.empty):
            progress = {"stage": "Evaluating every eligible MarketScope stock"}
            try:
                with st.spinner(
                    "Evaluating all eligible stocks and rebuilding both Top 5 per Sector tables…"
                ):
                    payload = calculate_rankings(
                        market.copy(deep=True),
                        list(years),
                        data_as_of,
                        monthly_loader,
                        live_loader,
                        threshold,
                        progress,
                    )
                st.session_state.t12_result = payload["result"]
                st.session_state.t12_histories = payload["histories"]
                st.session_state.t12_fingerprint = fingerprint
                st.session_state.t12_portfolios = {}
                st.session_state.t12_save_messages = []
                st.session_state.t12_show_full_analysis = True
                st.session_state.t12_save_job = SAVE_EXECUTOR.submit(
                    save_histories, payload["histories"]
                )
            except Exception as exc:
                logging.getLogger(__name__).exception("Top 5 per Sector calculation failed")
                st.session_state.t12_error = (
                    str(exc)
                    if isinstance(exc, ValueError)
                    else "Top 5 per Sector calculation could not be completed. The saved table above remains available."
                )

    consume_completed_job()
    if st.session_state.get("t12_error"):
        st.error(st.session_state.t12_error)
    for ok, message in st.session_state.get("t12_save_messages", []):
        if not ok:
            st.warning(message)

    if not st.session_state.get("t12_show_full_analysis"):
        return

    result = st.session_state.get("t12_result")
    if not result:
        return
    if st.session_state.get("t12_fingerprint") != fingerprint:
        st.warning(
            "Market data changed since the advanced recalculation. Recalculate again for a current full analysis."
        )

    table = result.get(kind)
    if not isinstance(table, pd.DataFrame) or table.empty:
        st.error(
            f"{kind} advanced results are incomplete. The saved table above remains available."
        )
        return
    detailed_history = st.session_state.get("t12_histories", {}).get(kind, history)
    st.divider()
    st.markdown("### Full recalculated analysis")
    render_ranked_table(
        kind,
        table,
        result,
        detailed_history,
        market,
        years,
        data_as_of,
        monthly_loader,
        live_loader,
        fingerprint,
    )


def render_ranked_table(
    kind, table, result, history, market, years, data_as_of,
    monthly_loader, live_loader, fingerprint,
):
    """A dedicated table and portfolio workspace for exactly one ranking kind."""
    st.subheader(
        "Top 5 per Sector Recession-Resilient Stocks"
        if kind == "Recession"
        else "Top 5 per Sector Max-Profit High-Performance Stocks"
    )
    st.warning(DISCLOSURES[kind])
    st.caption(f"{len(table)} selected stocks across {table.Sector.nunique()} sectors; up to five per sector.")
    st.caption(str(result["metadata"]))
    for warning in result.get("warnings", []):
        st.caption(warning)
    preferred = [
        "Rank",
        "Symbol",
        "Name",
        "Sector",
        "Price",
        kind + " Score",
        "Data Confidence",
        "Why Selected",
    ]
    metrics = (
        [
            "Defense Score",
            "Drawdown Score",
            "Recovery Score",
            "Bear Model Score",
            "Worst Stress Return %",
            "Maximum Drawdown %",
            "Recovery Periods",
            "Recovery Basis",
            "Stress Events",
            "Positive Years %",
        ]
        if kind == "Recession"
        else [
            "Historical Performance Score",
            "Future Projection Score",
            "Future P50 Score",
            "Future P75 Score",
            "5Y CAGR %",
            "10Y CAGR %",
            "Best Historical Year %",
            "Worst Historical Year %",
            "P50 Projected Profit",
            "P75 Projected Profit",
            "Positive Years %",
            "Maximum Drawdown %",
        ]
    )
    quantiles = [
        ("Bear " if kind == "Recession" else "") + f"P{q} Future Return %"
        for q in PERCENTILES
    ]
    # Put the actual ranking factors first, then the supporting evidence.
    factor_columns = (
        [
            "Rank", "Symbol", "Name", "Sector", "Price", "Recession Score",
            "Defense Score", "Drawdown Score", "Recovery Score", "Bear Model Score",
            "Consistency Score", "Current Strength Score", "Profitability Score",
            "Risk Penalty", "Recession Additional Penalty",
            "Worst Stress Return %", "Maximum Drawdown %",
            "Recovery Periods", "Recovery Basis",
            "Bear P10 Future Return %", "Bear P25 Future Return %",
            "Positive Years %", "Historical CAGR %",
            "Data Confidence", "Why Selected",
        ]
        if kind == "Recession"
        else [
            "Rank", "Symbol", "Name", "Sector", "Price", "Max Profit Score",
            "Historical Performance Score", "Recent Performance Score",
            "Future P50 Score", "Future P75 Score", "Fundamentals Score",
            "Consistency Score", "Relative Strength Score", "Downside Quality Score",
            "Risk Penalty",
            "3Y CAGR %", "5Y CAGR %", "10Y CAGR %",
            "P10 Future Return %", "P25 Future Return %",
            "P50 Future Return %", "P75 Future Return %",
            "Positive Years %", "Maximum Drawdown %",
            "Data Confidence", "Why Selected",
        ]
    )
    available = [column for column in factor_columns if column in table.columns]
    display = table[available].rename(columns=PERSISTED_TABLE_RENAMES)
    if "Consistency Score" in display.columns:
        display = display.rename(
            columns={
                "Consistency Score": (
                    "Consistency Score (10%)"
                    if kind == "Recession"
                    else "Consistency Score (5%)"
                )
            }
        )
    st.dataframe(
        display,
        hide_index=True,
        column_config=_ranking_factor_config(display),
        width="stretch",
        key="top12_" + kind.lower().replace(" ", "_") + "_ranked_table",
    )
    st.caption(
        "Factor-score columns are the exact 0-100 components used in the selected ranking formula; the percentage in "
        "each factor header is its formula weight. Raw CAGR, drawdown, stress and projection columns show the evidence "
        "behind those components. Projection returns are five-year annualized outcomes. Recovery is unavailable when "
        "the prior high has not been recovered."
    )
    sectors = table.groupby("Sector").size().rename("Stocks").reset_index()
    sectors["Status"] = sectors.Stocks.map(
        lambda n: "SECTOR CAP REACHED" if n == 5 else ""
    )
    st.dataframe(sectors, hide_index=True)
    with st.expander("All candidate scores and model audit"):
        st.dataframe(result["all_scores"], hide_index=True)
        st.json(result["market_state"])
    with st.expander("Walk-forward validation"):
        st.warning(LIMITATION)
        if st.button("Run historical study", key="t12_run_backtest"):
            with st.spinner("Rebuilding historical rankings from truncated data…"):
                st.session_state.t12_study = cached_backtest(market, list(years))
        study = st.session_state.get("t12_study")
        if isinstance(study, pd.DataFrame) and not study.empty:
            st.dataframe(study, hide_index=True)
            subset = study.loc[study.Ranking.eq(kind)]
            st.metric(
                "Exploratory backtest hit-rate score",
                f"{(subset['Return %']>subset['Universe Median %']).mean()*100:.1f}/100",
            )
        else:
            st.caption(
                "Model Backtest Score: unavailable until historical study completes."
            )
    st.markdown("#### Build sector-leader portfolio")
    allocation = st.radio(
        "Allocation",
        ["Equal Weight", "Score Weighted"],
        key="t12_input_allocation",
        horizontal=True,
    )
    investment = st.number_input(
        "Starting investment",
        min_value=1000.0,
        value=300000.0,
        key="t12_input_investment",
    )
    horizon = st.number_input(
        "Future years", min_value=1, max_value=50, value=10, key="t12_input_years"
    )
    inputs = portfolio_inputs(table, kind, allocation, investment, horizon)
    portfolio_key = hashlib.sha256(
        json.dumps(inputs, sort_keys=True).encode() + fingerprint.encode()
    ).hexdigest()
    if st.button("Build Sector-Leader Portfolio", key="t12_build"):
        with st.spinner("Running both portfolio maintenance strategies…"):
            try:
                try:
                    live_context = live_loader(tuple(inputs["holdings"]))
                except Exception:
                    live_context = {}
                projected = run_future_projection(
                    market,
                    inputs,
                    list(years),
                    monthly_returns=monthly_loader(
                        tuple(inputs["holdings"]), tuple(years)
                    ),
                    live_context=live_context,
                    data_as_of=data_as_of,
                )
                st.session_state.setdefault("t12_portfolios", {})[
                    portfolio_key
                ] = projected
            except Exception:
                st.error(
                    "Portfolio projection unavailable with this evidence. Check historical data and retry."
                )
    portfolio = st.session_state.get("t12_portfolios", {}).get(portfolio_key)
    if portfolio:
        cols = st.columns(2)
        for col, (strategy, payload) in zip(cols, portfolio["strategies"].items()):
            with col:
                st.markdown("**" + strategy + "**")
                summary = payload["summary"]
                for q in PERCENTILES:
                    st.metric(
                        f"P{q} Ending Balance",
                        f"${summary[f'P{q} Ending Balance']:,.0f}",
                    )
                for label in [
                    "Median Total Wealth Profit",
                    "Median Total Wealth Return",
                    "Probability Positive Total Wealth",
                    "Modeled Annualized Portfolio Volatility",
                    "Maximum Projected Drawdown",
                ]:
                    value = summary.get(label)
                    st.metric(
                        label, f"{value:,.2f}" if value is not None else "Unavailable"
                    )
                st.dataframe(payload["table"], hide_index=True)
        st.caption(
            "Correlation risk: "
            + str(
                portfolio.get("current_market_state", {}).get(
                    "portfolio_correlation_risk", "Unavailable"
                )
            )
        )
        sector_weights = (
            table.assign(Weight=table.Symbol.map(inputs["allocations"]))
            .groupby("Sector")
            .Weight.sum()
        )
        st.dataframe(sector_weights.rename("Allocation %"))
        if kind == "Recession":
            st.info(
                "Bear/stress portfolio: P10/P25/P50 and drawdown above use the governed Stress Test profile."
            )
    study = st.session_state.get("t12_study")
    try:
        excel, pdf = ranking_exports(kind, table, result, portfolio, history, study)
    except Exception:
        logging.getLogger(__name__).exception("Top 5 per Sector export generation failed")
        st.warning(
            "Reports could not be generated. The ranked table above remains available; retry after checking the server log."
        )
        return
    st.download_button(
        "Download Excel",
        excel,
        file_name="MarketScope_SectorLeaders_" + kind.replace(" ", "_") + ".xlsx",
    )
    st.download_button(
        "Download PDF",
        pdf,
        file_name="MarketScope_SectorLeaders_" + kind.replace(" ", "_") + ".pdf",
    )
    with st.expander("View Ranking History"):
        st.dataframe(pd.DataFrame(history.get("events", [])), hide_index=True)
