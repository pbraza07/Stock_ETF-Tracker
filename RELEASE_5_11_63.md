# MarketScope 5.11.63

- Searchable task-based workspace navigation, with Market News first and Alerts & Help last.
- Existing route keys, calculations, precision settings, exports and saved session results preserved.
- Ranking summary view with full factor evidence and source-date columns available via toggle.
- News archive initialization queued in the background rather than blocking the session.
- Responsive control sizing, metric typography and wrapping.

Verification: new Streamlit navigation/retention and bootstrap deduplication tests pass. Full source-repository regression suite compared to unchanged baseline; packaging tests intentionally expect data files absent and are incompatible with the live-data repository checkout. No live data files were deleted to satisfy these tests.

Limitations: complete mobile browser verification and controlled end-to-end before/after timings are not available. No quantified speed improvement is claimed. Render wake-up delay is excluded by request. This release improves navigation and cold news initialization; existing background simulation workers are preserved.
