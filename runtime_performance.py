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
    """Keep keyed input widgets across lazy pages, never write button triggers.

    Metadata access is covered by navigation tests and the pinned Streamlit version.
    Non-widget session values already persist without reassignment.
    """
    from streamlit.runtime.state import get_session_state
    state=get_session_state()._state
    forbidden={'trigger_value','string_trigger_value','chat_input_value','json_trigger_value','file_uploader_state_value'}
    for key in list(st.session_state):
        widget_id=state._key_id_mapper.get_id_from_key(key,None)
        metadata=state._get_widget_metadata(widget_id) if widget_id else None
        if metadata is not None and metadata.value_type not in forbidden:
            st.session_state[key]=st.session_state[key]
