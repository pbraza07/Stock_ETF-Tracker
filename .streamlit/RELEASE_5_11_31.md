# MarketScope 5.11.31 — Self-contained interactive recession charts

The interactive checkbox previously selected Streamlit's Plotly frontend component, the path implicated in the user's repeated browser JavaScript SyntaxError. It now renders a self-contained app-generated HTML component with the installed Plotly JavaScript bundled inline. No CDN or Streamlit Plotly lazy-loader is needed. This is an app-generated graph, not an embedded FRED page.

The original figure data and layout are reused: recession shading, dark styling, monthly dates, missing-data gaps, Sahm threshold and all history windows. Hover, drag zoom, wheel zoom, pan, reset and PNG download are enabled. An SVG remains visible until Plotly finishes successfully; script errors leave that fallback available with a status message. The unchecked SVG view and the v5.11.30 date-overflow fix are preserved.

Validation: 646 existing regression tests passed, plus 12 new self-contained interactive-document tests (three series times four history settings). All nine generated inline script blocks across three All-history examples passed Node JavaScript syntax validation. Checkbox integration asserts three HTML components and no use of the failing native Plotly component.

Limitation: Cloud browser blocked the local preview with ERR_BLOCKED_BY_CLIENT. Actual hover/zoom and production-browser verification remain pending. No claim is made that the original browser/network root cause was established.

Deploy extracted files while preserving existing data. Include recession_interactive.py and recession_indicators.py. No new dependencies or secrets. GitHub/Render have not been modified by this delivery.
