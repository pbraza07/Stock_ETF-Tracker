"""Official Investing.com weekly calendar widget, high importance only."""
from urllib.parse import urlencode


def calendar_url():
    return 'https://sslecal2.investing.com/?'+urlencode({
        'columns':'exc_flags,exc_currency,exc_importance,exc_actual,exc_forecast,exc_previous',
        'importance':'3', 'calType':'week', 'timeZone':'8', 'lang':'1',
        'features':'timezone', 'ecoDayBackground':'#0C1824','defaultFont':'#F2F7FB',
        'innerBorderColor':'#27465A','borderColor':'#27465A','ecoDayFontColor':'#56E58B'})


def render_economic_calendar():
    import streamlit as st
    import streamlit.components.v1 as components
    st.subheader('This week’s economic calendar — ★★★ high importance')
    st.caption('Announcement times default to Eastern Time (US & Canada). Use the calendar timezone control for local times. Global events; three-star importance only.')
    components.iframe(calendar_url(),height=520,scrolling=True)
    st.markdown('Economic Calendar provided by [Investing.com](https://www.investing.com/economic-calendar/). If the embedded calendar is blocked by your browser, open the source calendar.')
