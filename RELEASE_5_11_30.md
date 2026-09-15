# MarketScope 5.11.30 — All-history date overflow fix

The v5.11.29 SVG chart's tick calculation multiplied the full historical Timedelta by an integer before dividing by five. With more than approximately 58 years of data this intermediate value exceeded the nanosecond Timedelta range. Reproduced the exact reported OverflowError using monthly observations from January 1959 through July 2026.

Tick placement now multiplies by a bounded fraction first. No oversized intermediate duration is created. Dates, observations, recession bands and calculations remain unchanged. Added coverage for all three indicators across All history, 5-, 10- and 20-year windows.

Replaced deprecated use_container_width arguments throughout production Python UI code with width='stretch' / width='content'. Audited Streamlit call signatures against the installed runtime.

The supplied Render log confirms build and deployment success. Yahoo YFRateLimitError and HTTP 401 Invalid Crumb are separate upstream stock-data restrictions, not a FRED error or an installation failure. This patch does not claim to resolve Yahoo access restrictions. No new secrets or dependencies are required.

Deploy extracted repository-root files while preserving existing data. Include recession_chart_svg.py, app.py and top12_ui.py. GitHub and Render have not been updated by this delivery. Production browser validation remains pending.
