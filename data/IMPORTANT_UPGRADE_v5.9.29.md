# MarketScope v5.9.29 — Sector Top Performers Logo Fix

- Fixes Sector Performance drill-down crash caused by an undefined `cached_instrument_logo_urls` reference.
- Sector top-performer panels now reuse the production `cached_logo_urls` pipeline used by Market Navigator and Comparison.
- Preserves stock logos when available and falls back cleanly when no remote logo is returned.
- No changes to sector ranking math, comparison math, PDFs, portfolio simulator, or annual-withdrawal calculations.
