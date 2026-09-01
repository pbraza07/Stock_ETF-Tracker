# MarketScope v5.9.60 — UI Visibility + Card Logo Restore

## 1. Source-priority implementation text removed

The text beginning with:

`Load actual month-end returns...`
`Source priority:`

was never intended as a user-facing message.

Root cause: `cached_actual_monthly_returns()` contained a standalone formatted triple-quoted string. Streamlit's magic-expression renderer treated that f-string as displayable content every time the function executed, so it appeared in multiple Portfolio Simulator paths.

v5.9.60 replaces that expression with internal comments. The app contains no standalone formatted string expression in that function and no `Source priority:` UI text.

## 2. Positive Months and KPI values never truncate

The Monthly Withdrawal summary no longer uses five native `st.metric()` cells. Streamlit's metric value CSS keeps values on one line and can show an ellipsis when a long value is placed in a narrow fifth column.

The new responsive KPI grid:
- shows the full monthly withdrawal
- shows the full Rebalanced remaining balance
- shows the full Not-Rebalanced remaining balance
- shows the full difference
- shows Positive Months on two explicit lines:
  - `RB positive / modeled`
  - `NR positive / modeled`
- uses wrapping and `overflow: visible`
- collapses to two columns and then one column on narrower screens

No value is intentionally suppressed.

## 3. Card View logos restored

Logo resolution is now:
1. Yahoo Search direct `logoUrl` when supplied
2. Yahoo/yfinance issuer metadata
3. issuer website favicon when Yahoo supplies the website
4. ticker-addressable image fallback
5. ticker initials only if the remote image itself fails

The batch logo request is reduced from six concurrent workers to three to lower Yahoo metadata throttling, and the cache TTL is reduced from 24 hours to 30 minutes so a temporary provider failure does not leave initials cached for an entire day.

The HTML logo element now has an explicit image-failure handler that reveals ticker initials only when the image cannot load.

## PDF version

The Portfolio PDF contract is bumped to v19 so opening/rebuilding a saved simulation carries the current MarketScope v5.9.60 version on page 1. No financial calculation methodology changed in this release.
