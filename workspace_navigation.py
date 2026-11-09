"""Task-based navigation; legacy route keys preserve all existing callbacks."""
from contextlib import nullcontext
import streamlit as st

NAMES = ["Market News", "Research · Find a stock", "Research · Sector rankings", "Plan · Portfolio simulator", "Plan · Future projections", "Research · Compare stocks & ETFs", "Research · Sector performance", "Economy · Recession indicators", "Research · Quality & growth", "Alerts & Help"]
GUIDANCE = ["Read market stories, or open the economic and earnings calendars.", "Search a ticker, then open its performance and analyst estimates.", "Open a saved sector ranking instantly; recalculate only when you need a new analysis.", "Choose your holdings and period, run the simulation, then review or export results.", "Set your planning inputs and run a projection. Review the outcome range and depletion risk together.", "Select instruments to compare their performance on the same basis.", "Compare sectors using the selected period.", "Explore economic evidence across the full available history.", "Review quality and return opportunities alongside missing criteria and risk.", "Review alerts and find explanations of data, models, and exports."]

class Workspace:
    def __init__(self, opened):
        self.open = opened
        self.context = st.container() if opened else nullcontext()
    def __enter__(self):
        return self.context.__enter__()
    def __exit__(self, *args):
        return self.context.__exit__(*args)

def render_navigation(labels):
    if st.session_state.get('workspace_navigation') not in labels:
        st.session_state['workspace_navigation'] = labels[0]
    selected = st.selectbox('Go to workspace', labels, key='workspace_navigation',
        format_func=lambda label: NAMES[labels.index(label)],
        help='Search or choose a workspace. Completed results and inputs remain available during this session.')
    index = labels.index(selected)
    st.markdown('### ' + NAMES[index])
    st.caption(GUIDANCE[index])
    st.markdown('''<style>
    .stButton button,.stDownloadButton button {min-height:44px;border-radius:10px;white-space:normal;}
    [data-testid="stMetricValue"] {font-variant-numeric:tabular-nums;font-size:clamp(1.3rem,2.5vw,2rem);}
    [data-testid="stCaptionContainer"] {color:#afc1d1;}
    [data-testid="stExpander"] {border-color:#294355;border-radius:12px;}
    @media(max-width:700px){.block-container{padding:1rem .85rem 3rem!important;}
    h1{font-size:1.8rem!important;}h2{font-size:1.45rem!important;}
    [data-testid="stHorizontalBlock"]{flex-wrap:wrap;gap:.7rem;}
    [data-testid="stColumn"]{min-width:min(100%,240px)!important;}
    button p{overflow-wrap:anywhere;}}
    </style>''', unsafe_allow_html=True)
    return [Workspace(label == selected) for label in labels]
