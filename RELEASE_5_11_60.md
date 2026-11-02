# MarketScope v5.11.60 — Analyst targets in both sector rankings

Both Top 5 per Sector Recession-Resilient and Max-Profit tables now show, immediately after Current Price:

- Target Price Low
- Target Price Median
- Target Price High
- Median Target Upside % = (reported median target / current price − 1) × 100
- Current Price Minus Low Target = current price − low target, in dollars
- Price As Of, Target Retrieved At, and Target Source

These are analyst stock-price targets, not guaranteed profit amounts or simulated P10/P50/P90 outcomes. Median is never substituted with the mean/average. Unavailable, nonpositive or nonfinite data remains blank. Zero quotes never cause division by zero.

The displayed Current Price uses the latest available app snapshot quote, with saved-quote fallback if needed. It is not labeled real time. Provider target data refreshes in a single background batch with a one-hour cache; source/cache failure does not hide rankings. Fresh partial responses are not spliced with independently dated older targets. Price and target dates are displayed independently.

The saved rank, scores, constituent ordering, and ranking-factor evidence are unchanged. These fields are presentation-only; analyst estimates do not become scoring inputs. Older saved ledgers receive the columns without requiring a ranking recalculation. Advanced ranking displays and their Excel/PDF reports include the new fields. Previously saved report files are not retroactively modified.

All earlier session retention, market loading, Favorite Picks fixes, portfolio tools, calendars, news and projections are preserved. Regression tests cover both ranking families, calculations and signs, true median versus mean, missing/invalid prices, partial responses, unchanged saved inputs, exports, and background/cache behavior.

Installation: update the repository from this package and deploy through the existing Render process. Confirm version 5.11.60. This package was not deployed to the live service while it was prepared. It contains no credentials or generated user state.
