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
from top12_jobs import EXECUTOR, calculate_rankings, save_histories


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
            st.session_state.t12_save_job = EXECUTOR.submit(
                save_histories, payload["histories"]
            )
        except Exception as exc:
            logging.getLogger(__name__).exception("Top 12 calculation failed")
            st.session_state.t12_error = (
                str(exc)
                if isinstance(exc, ValueError)
                else "Top 12 calculation failed. Your previous result is retained. Retry the button; technical details were recorded in the server log."
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


@st.fragment(run_every="1s")
def watch_ranking_jobs():
    job = st.session_state.get("t12_job")
    saved = st.session_state.get("t12_save_job")
    if (job and job["future"].done()) or (saved and saved.done()):
        consume_completed_job()
        st.rerun()
    if job:
        st.info(
            job["progress"]["stage"]
            + ". You can leave this tab and return; calculation continues."
        )
    elif saved:
        st.caption("Results ready. Saving the change history in the background…")


@st.cache_data(ttl=60, max_entries=4, show_spinner=False)
def cached_ledger(kind):
    return load_ledger(kind)


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
    consume_completed_job()
    st.markdown("### Dynamic Top 12 Stock Rankings")
    c = st.columns(2)
    busy = bool(st.session_state.get("t12_job"))
    rb = c[0].button(
        "🛡 Top 12 Recession-Resilient Stocks",
        key="t12_recession",
        disabled=busy,
        on_click=request_ranking,
        args=("Recession",),
    )
    mp = c[1].button(
        "🚀 Top 12 Max-Profit High-Performance Stocks",
        key="t12_profit",
        disabled=busy,
        on_click=request_ranking,
        args=("Max Profit",),
    )
    threshold = st.number_input(
        "Replacement threshold (ranking points)",
        0.0,
        10.0,
        1.0,
        0.25,
        key="t12_input_threshold",
    )
    fingerprint = hashlib.sha256(
        pd.util.hash_pandas_object(market, index=True).values.tobytes()
        + str(data_as_of).encode()
    ).hexdigest()
    pending_request = st.session_state.get("t12_pending_request")
    if pending_request and not st.session_state.get("t12_job"):
        st.session_state.t12_input_view = pending_request
        st.session_state.pop("t12_error", None)
        progress = {"stage": "Starting ranking calculation"}
        st.session_state.t12_job = {
            "future": EXECUTOR.submit(
                calculate_rankings,
                market.copy(deep=True),
                list(years),
                data_as_of,
                monthly_loader,
                live_loader,
                threshold,
                progress,
            ),
            "fingerprint": fingerprint,
            "progress": progress,
        }
        # Acknowledge only after the job exists. Never rely on rb/mp above to
        # remember intent; those values are false after an intervening rerun.
        st.session_state.pop("t12_pending_request", None)
    consume_completed_job()
    if st.session_state.get("t12_job") or st.session_state.get("t12_save_job"):
        watch_ranking_jobs()
    if st.session_state.get("t12_error"):
        st.error(st.session_state.t12_error)
    for ok, message in st.session_state.get("t12_save_messages", []):
        if not ok:
            st.warning(message)
    result = st.session_state.get("t12_result")
    if not result:
        if not st.session_state.get("t12_job") and not st.session_state.get(
            "t12_error"
        ):
            st.info("Choose a Top 12 button to display its ranked table here.")
        return
    if st.session_state.get("t12_fingerprint") != fingerprint:
        st.warning(
            "Market data changed. Click either ranking button to recalculate this saved view."
        )
    kind = st.radio(
        "Ranking view", list(DISCLOSURES), key="t12_input_view", horizontal=True
    )
    table = result[kind]
    history = st.session_state.get("t12_histories", {}).get(kind, {})
    st.subheader(
        "Top 12 Recession-Resilient Stocks"
        if kind == "Recession"
        else "Top 12 Max-Profit High-Performance Stocks"
    )
    st.warning(DISCLOSURES[kind])
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
    config = {
        "Rank": st.column_config.NumberColumn(pinned=True),
        "Symbol": st.column_config.TextColumn("Ticker", pinned=True),
        "Price": st.column_config.NumberColumn("Current Price", format="$%.2f"),
    }
    for col in table:
        if "%" in col:
            config[col] = st.column_config.NumberColumn(format="%.2f%%")
    st.dataframe(
        table[preferred + metrics + quantiles],
        hide_index=True,
        column_config=config,
        width="stretch",
    )
    st.caption(
        "Projection returns are five-year annualized outcomes. Projected dollar profits use $100,000 per security. Recovery is unavailable when the prior high has not been recovered."
    )
    sectors = table.groupby("Sector").size().rename("Stocks").reset_index()
    sectors["Status"] = sectors.Stocks.map(
        lambda n: "SECTOR CAP REACHED" if n == 4 else ""
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
    st.markdown("#### Build 12-stock portfolio")
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
    if st.button("Build 12-Stock Portfolio", key="t12_build"):
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
        logging.getLogger(__name__).exception("Top 12 export generation failed")
        st.warning(
            "Reports could not be generated. The ranked table above remains available; retry after checking the server log."
        )
        return
    st.download_button(
        "Download Excel",
        excel,
        file_name="MarketScope_Top12_" + kind.replace(" ", "_") + ".xlsx",
    )
    st.download_button(
        "Download PDF",
        pdf,
        file_name="MarketScope_Top12_" + kind.replace(" ", "_") + ".pdf",
    )
    with st.expander("View Ranking History"):
        st.dataframe(pd.DataFrame(history.get("events", [])), hide_index=True)
