"""Presentation of the last complete session calculation when a draft is invalid.

No TTL, shared user cache or financial recalculation. Normal session teardown
releases these values; saved portfolio records are managed separately.
"""
def render_retained_portfolio(snapshot):
    import pandas as pd
    import streamlit as st
    st.info("The current inputs/data cannot produce a complete result. Your last completed portfolio remains below.")
    st.caption("Last completed portfolio • " + str(snapshot.get("portfolio_period", ""))
        + " • Data as of " + str(snapshot.get("data_as_of", "Unavailable"))
        + " • Holdings: " + ", ".join(snapshot.get("selected_portfolio_symbols", [])))
    cols = st.columns(4)
    for col, label, key, fmt in zip(cols,
        ["Beginning balance", "Ending balance", "Profit / loss", "Return"],
        ["portfolio_total", "total_ending", "total_profit", "total_return"],
        ["${:,.2f}", "${:,.2f}", "${:+,.2f}", "{:+.2f}%"]):
        col.metric(label, fmt.format(snapshot.get(key, 0)))
    st.dataframe(pd.DataFrame(snapshot["portfolio_results"]), hide_index=True, width="stretch")
    # Preserve full withdrawal evidence, including nested tables and summary fields.
    for key, label in [
        ("portfolio_withdrawal_rebalanced_result", "Yearly — Rebalanced"),
        ("portfolio_withdrawal_not_rebalanced_result", "Yearly — Not Rebalanced"),
        ("portfolio_monthly_withdrawal_rebalanced_result", "Monthly — Rebalanced"),
        ("portfolio_monthly_withdrawal_not_rebalanced_result", "Monthly — Not Rebalanced")]:
        value = snapshot.get(key)
        if value:
            with st.expander(label + " — last completed result"):
                st.write(value)
    st.caption("Saved / Manage uses this completed snapshot until valid inputs produce a replacement. Draft values are not applied to these results.")
