# MarketScope 5.11.67 — workspace loading

- Removed the perpetual three-second source-status polling that repeatedly activated the running indicator.
- No automatic full-script rerun when shared background requests complete. Offer an explicit Show updated source data button, preserving the active view and calculated results.
- Recession navigation reads validated saved snapshots immediately. FRED checks use two background threads, single-flight requests, last-good preservation and failure backoff. Check completed recession downloads retrieves ready results without launching duplicate downloads.
- Reuse exact-input market assembly within each session. Full snapshot, symbols, universe metadata and per-session overrides form the fingerprint. Copy-on-read prevents accidental mutation. Live quote overlays continue separately.
- No changes to ranking formulas, projection precision, source selection or investment calculations.

Validation: targeted navigation, cache, background jobs and preserved-data tests; exact DataFrame equality on 375 actual saved symbols. Local 20-run mean market assembly: 21.68 ms before, 0.62 ms warm after. This is only the preparation component, not an end-to-end browser loading claim. Streamlit rendering, network latency and initial hosting wake-up can still take time.
