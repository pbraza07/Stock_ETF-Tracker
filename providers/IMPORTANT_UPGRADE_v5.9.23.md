# MarketScope v5.9.23 — Stock & ETF Comparison Selection State Fix

## Critical fix
The v5.9.22 comparison multiselect was unintentionally reset from the older `compare_symbols` session-state value before Streamlit could commit a newly selected ticker. On mobile this appeared as a successful tap followed immediately by `0 instrument(s) selected`, so Comparison Cards and Comparison Table never rendered.

## New state contract
- `stock_compare_selector` is the authoritative user-input control.
- Its `on_change` callback commits the complete selected set to `compare_symbols`.
- The app never overwrites a fresh selector choice with stale comparison state.
- Stale-symbol cleanup only removes symbols that no longer exist in the current universe.
- Selected instruments immediately drive Comparison Cards, Comparison Table, Yahoo/company logo retrieval, targets, ratings, prices and all existing comparison analytics.

All v5.9.22 PDF first-page data, server persistence, Share PDF, and Back to MarketScope behavior are preserved.
