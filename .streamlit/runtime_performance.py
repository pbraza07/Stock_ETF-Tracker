"""Bounded caches for presentation only; no investment mathematics."""

import streamlit as st
from future_projection import build_csv_export, build_excel_export, build_pdf_export
from top12_exports import build_top12_excel, build_top12_pdf


@st.cache_data(ttl=900, max_entries=8, show_spinner=False)
def projection_exports(result):
    return (
        build_excel_export(result),
        build_csv_export(result),
        build_pdf_export(result),
    )


@st.cache_data(ttl=900, max_entries=8, show_spinner=False)
def ranking_exports(kind, table, result, portfolio, history, backtest):
    return build_top12_excel(
        kind, table, result, portfolio, history, backtest
    ), build_top12_pdf(kind, table, result, portfolio, history, backtest)


def preserve_navigation_state():
    for key in list(st.session_state):
        if str(key).startswith(("fp_", "t12_input_")):
            st.session_state[key] = st.session_state[key]
