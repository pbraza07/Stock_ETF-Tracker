# MarketScope v5.9.26

- Fixed StreamlitDuplicateElementKey in Stock & ETF Comparison by namespacing all return/profit tile state and widget keys by view.
- Market Navigator and Comparison can now render the same ticker simultaneously without duplicate profit-tile keys.
- Sector Performance stock-count controls are clickable and open a Top Performers drill-down for the selected sector.
- Sector drill-down ranks the top 10 stocks by the currently selected sector ranking period and includes logo, ticker, name, analyst rating, current price, selected-period return, YTD, 1Y, average analyst target, implied target upside, and market cap.
