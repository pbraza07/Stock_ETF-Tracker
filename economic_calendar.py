"""Official Investing.com weekly calendar widget, high importance only."""
from urllib.parse import urlencode


def calendar_url():
    return 'https://sslecal2.investing.com/?'+urlencode({
        'columns':'exc_flags,exc_currency,exc_importance,exc_actual,exc_forecast,exc_previous',
        'importance':'3', 'countries':'5', 'calType':'week', 'timeZone':'8', 'lang':'1',
        'features':'timezone', 'ecoDayBackground':'#E5E7EB','defaultFont':'#111827',
        'innerBorderColor':'#CBD5E1','borderColor':'#CBD5E1','ecoDayFontColor':'#111827'})


def calendar_embed():
    # The provider controls the cross-origin document. Filter the whole iframe,
    # including its white body/rows, instead of changing only header/text colors.
    from html import escape
    return '<style>html,body{margin:0;background:#06101A}iframe{width:100%;height:520px;border:0;filter:invert(.94) hue-rotate(180deg);color-scheme:light}</style><iframe title="United States high-importance economic calendar" src="'+escape(calendar_url(),quote=True)+'"></iframe>'


def render_economic_calendar():
    import streamlit as st
    import streamlit.components.v1 as components
    st.subheader('This week’s U.S. economic calendar — ★★★ high importance')
    st.caption('United States only; three-star importance only. Announcement times default to Eastern Time (US & Canada). Use the calendar timezone control for local times.')
    components.html(calendar_embed(),height=525,scrolling=False)
    st.markdown('Economic Calendar provided by [Investing.com](https://www.investing.com/economic-calendar/). If the embedded calendar is blocked by your browser, open the source calendar.')
