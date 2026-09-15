# MarketScope v5.9.9 — Collapsible Controls, Stock + ETF Comparison, Smooth Card Profit

- Instrument Comparison now supports both Stocks and ETFs with no artificial selection cap.
- Every stock and ETF card has a Compare toggle; ETF cards retain Holdings as a separate action.
- Buy Signal Alerts are collapsed by default and open only from the Buy Signal Alerts button.
- Portfolio Split Simulator is collapsed by default and toggles open/closed from its own button.
- Save / Manage Portfolio Simulations is independently collapsed and toggles open/closed from its own button.
- The Investment Simulator is placed immediately above Display Mode.
- Card timeframe/year profit calculations now use a Streamlit fragment-local period selector. Selecting 1D, 1M, 3M, 6M, YTD, or any displayed calendar year updates only that card's profit area without query-string navigation, page jumps, or a full-app rerun.
- Existing Card View, Table View, saved PDF library, ETF holdings, live charts, analyst targets, news, annual returns, portfolio simulator, and 213-ETF universe are preserved.
