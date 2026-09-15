# MarketScope v5.9.1 — ETF Card Rendering + Stock Sector Fix

This patch fixes the v5.9 ETF card rendering regression where HTML tags could appear as visible text inside ETF cards.

## Root cause
v5.9 inserted the stock-only analyst price-target block inside an indented triple-quoted Streamlit Markdown block. For ETFs that helper returns an empty string. The resulting blank line could terminate the HTML block, causing the remaining indented card markup to be interpreted as code text.

## Fix
- Card HTML is now assembled as one continuous compact HTML string before being passed to `st.markdown(..., unsafe_allow_html=True)`.
- ETF cards no longer expose raw `<div ...>` markup.
- Stock cards now show their Sector directly under the company name.
- ETF card naming behavior remains unchanged: use the ETF `Sector` value when available; otherwise fall back to the fund name.

No market methodology, ETF universe, price target logic, live chart logic, or scheduled refresh behavior was changed.
