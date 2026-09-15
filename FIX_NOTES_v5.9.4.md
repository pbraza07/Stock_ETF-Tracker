# v5.9.4 Feature Notes

## Card / Table display tabs
- Added an actual Streamlit tab switch between **Card View** and **Table View**.
- Both views inherit the same universe, quick filters, search, analyst-rating filters, sector filters and buy-signal filters.

## Table View
- Shows all filtered instruments without card pagination.
- Includes current card/intelligence data: identity, sector/industry, price, market cap, analyst rating, stock target range, target implied move, buy signals, short-horizon returns, YTD, ten calendar-year returns, and current investment simulation results.
- Explicit sort controls support price, market cap, analyst rating, price target, implied move, profit, simulation return and every performance period/year.
- Native Streamlit header-click sorting remains available.
- Removed/hidden metadata columns stay removed: NAV, Exchange, Inception Date, Return Basis, Rating Source, Data As Of, Rating Update ET and Snapshot Update ET.
