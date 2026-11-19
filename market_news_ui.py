"""Display only headlines found on the configured financial websites."""
from pathlib import Path
from urllib.parse import urlsplit
import json
import streamlit as st
from scraped_news import SITES, collect_pages

SNAPSHOT = Path(__file__).parent / "data/web_headlines.json"


@st.cache_data(ttl=900, show_spinner=False)
def current_pages():
    seed = json.loads(SNAPSHOT.read_text()) if SNAPSHOT.exists() else {}
    return collect_pages(seed)


@st.fragment(run_every="15m")
def render_market_news():
    with st.spinner("Checking news websites…"):
        pages = current_pages()
    selected = st.selectbox("News source", ["All sources", *SITES])
    query = st.text_input("Search headlines").strip().casefold()
    with st.expander("Source availability"):
        st.table([{"Site": name, "Latest check": entry["status"], "Checked (UTC)": entry["checked"],
                   "Headlines collected (UTC)": entry.get("collected") or "Unavailable"}
                  for name, entry in pages.items()])
    matched = False
    for name, entry in pages.items():
        if selected not in ("All sources", name):
            continue
        rows = [r for r in entry["rows"] if query in r["title"].casefold()]
        if not rows and selected == "All sources":
            continue
        st.subheader(name)
        if entry["status"] != "Available":
            st.caption(entry["status"] + (f" · Showing headlines collected {entry['collected']}" if rows else ""))
        for row in rows:
            matched = True
            st.link_button(row["title"], row["url"], help=urlsplit(row["url"]).hostname)
    if not matched:
        st.info("No headlines match this selection.")
