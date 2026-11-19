"""Display only headlines found on the configured financial websites."""
from pathlib import Path
from urllib.parse import urlsplit
from hashlib import sha256
from html import escape
import json
import streamlit as st
from news_context import story_context, impact_html
from scraped_news import SITES, collect_pages

SNAPSHOT = Path(__file__).parent / "data/web_headlines.json"


@st.cache_data(ttl=900, show_spinner=False)
def current_pages():
    seed = json.loads(SNAPSHOT.read_text()) if SNAPSHOT.exists() else {}
    return collect_pages(seed)


@st.dialog("Story details")
def read_story(row, source, context):
    st.text(row["title"])
    st.caption(f"Listed by {source} · {urlsplit(row['url']).hostname}")
    if row.get("excerpt"):
        st.text(row["excerpt"])
    for label, impacts in (("Stock", context["stocks"]), ("Sector", context["sectors"]),
                           ("Market", [context["market"]])):
        for item in impacts:
            st.write(f"{label} · {item['name']}")
            st.caption(item["reason"].replace("feed item", "headline or excerpt"))
    st.link_button("Read original article", row["url"])


def story_card(row, source, collected):
    context = story_context(row)
    with st.container(border=True):
        date = ("Published " + row["published_at"] if row.get("published_at")
                else "Collected " + (collected or "at an unknown time"))
        st.caption(f"{source} · {urlsplit(row['url']).hostname} · {date}")
        st.markdown(impact_html(context), unsafe_allow_html=True)
        st.markdown("<strong>" + escape(row["title"]) + "</strong>", unsafe_allow_html=True)
        if row.get("excerpt"):
            st.text(row["excerpt"])
        key = sha256((source + row["url"]).encode()).hexdigest()
        if st.button("View story details", key="news_card_" + key, width="stretch"):
            read_story(row, source, context)


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
            story_card(row, name, entry.get("collected"))
    if not matched:
        st.info("No headlines match this selection.")
