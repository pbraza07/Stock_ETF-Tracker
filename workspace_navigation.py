"""Task-based navigation; legacy route keys preserve all existing callbacks."""
from contextlib import nullcontext
import streamlit as st

# Keep the route values stable for links from other workspaces.
DESTINATIONS = {
    "📰 Market News": ("Markets", "Market news", "Browse headlines by source or search for a company or topic."),
    "Recession Indicators": ("Markets", "Economy signals", "Explore indicators that track changes in the economy over time."),
    "◈ Market Navigator": ("Research", "Find a stock", "Enter a company’s ticker (its trading symbol) to see past returns and analyst estimates."),
    "⚖ Stock & ETF Comparison": ("Research", "Compare investments", "Choose stocks or exchange-traded funds (ETFs) to compare over the same dates."),
    "Favorite Picks": ("Research", "Sector rankings", "See how stocks rank within each industry group, or run a fresh ranking."),
    "◈ Sector Performance": ("Research", "Compare sectors", "Choose a time period to compare returns across industry groups."),
    "Quality Growth & Return Opportunities": ("Research", "Find quality and growth stocks", "Explore companies by growth, financial quality and risk."),
    "◫ Portfolio Simulator": ("Plan", "Test a portfolio", "Choose investments and past dates to see how a mix of holdings would have performed."),
    "Future Projection": ("Plan", "Explore future outcomes", "Enter your holdings and withdrawals to explore a range of possible future balances."),
    "🔔 Alerts & Help": ("Help", "Alerts and help", "Review alerts and learn how MarketScope calculates results and exports reports."),
}


class Workspace:
    def __init__(self, opened):
        self.open = opened
        self.context = st.container() if opened else nullcontext()
    def __enter__(self):
        return self.context.__enter__()
    def __exit__(self, *args):
        return self.context.__exit__(*args)

def render_navigation(labels):
    state = st.session_state
    current = state.get("workspace_navigation")
    if current not in labels:
        current = labels[0]
    groups = {}
    for route, (group, _, _) in DESTINATIONS.items():
        if route in labels:
            groups.setdefault(group, []).append(route)

    def change_section():
        group = state["investor_section"] or DESTINATIONS[state["workspace_navigation"]][0]
        remembered = state.get("investor_recent", {}).get(group)
        state["workspace_navigation"] = remembered if remembered in groups[group] else groups[group][0]

    def change_tool():
        state["workspace_navigation"] = state["investor_tool"]

    group, title, guidance = DESTINATIONS[current]
    state.setdefault("investor_recent", {})[group] = current
    state["workspace_navigation"] = current
    state["investor_section"] = group
    st.segmented_control("Explore MarketScope", list(groups), key="investor_section",
                         on_change=change_section, width="stretch")
    if len(groups[group]) > 1:
        state["investor_tool"] = current
        st.selectbox(f"{group} tools", groups[group], key="investor_tool",
                     format_func=lambda route: DESTINATIONS[route][1], on_change=change_tool)
    st.header(title)
    st.caption(guidance)
    return [Workspace(label == current) for label in labels]
