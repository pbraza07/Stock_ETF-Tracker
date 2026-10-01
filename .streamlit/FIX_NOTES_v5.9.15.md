# MarketScope v5.9.15 — v5.9.7 Card Look + Reliable Click-to-Profit Fix

## Fixed

- Restored the **Card View information layout and visual treatment to the v5.9.7 style**: dark futuristic card shell, compact 3-column return ladder, analyst targets, investment result, rating and signal presentation.
- Every return period displayed on the card is now a **native Streamlit button** rather than query-string/link navigation.
- Return-period selection now uses an `on_click` callback that writes the selected period to `st.session_state` **before** the card fragment reruns.
- The selected return period is used directly by the exact-period profit formula:
  - Ending value = Investment × (1 + Selected Return % / 100)
  - Profit / Loss = Ending value − Investment
- Clicking a period reruns **only that card-local fragment**, keeping the interaction smooth and avoiding a full-page jump or reload.
- The return tiles, selected-period profit output, investment summary, rating and signal remain **inside the same card boundary**.
- Card action controls remain below the card, matching the familiar v5.9.7 organization.

## Preserved

- Card View and Table View search.
- Sidebar removal from v5.9.13.
- 213 ETF universe.
- Stock/ETF filters, sorting, pagination, analyst targets, News, Holdings, Compare, portfolio simulator, saved simulations and PDF reporting.
