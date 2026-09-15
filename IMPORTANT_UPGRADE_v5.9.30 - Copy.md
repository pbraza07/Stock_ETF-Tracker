# MarketScope v5.9.30 — Sector Drill-Down Button + Duplicate Column Fix

Parent release: v5.9.29.

## Fixes

1. Sector Top Performers tables now build a unique ordered column list, preventing PyArrow/Streamlit `ValueError: Duplicate column names found` when the active ranking period is already YTD or 1Y.
2. The **Stocks** KPI in every Sector Performance card is now the interactive drill-down button. It shows the number of stocks and `View top performers` in the same control.
3. The old duplicate button below each sector card has been removed.

## Preserved behavior

Top Performer drill-downs remain stock-only and keep logos, symbol, name, analyst rating, current price, selected-period return, YTD, 1Y, average target, implied target upside, and market cap.
