# MarketScope 5.11.55 — GDP-Based Recession Indicator

Added James Hamilton's GDP-Based Recession Indicator Index (JHGDPBRINDX)
as the fourth chart in Recession Indicators. Source and interpretation:
https://fred.stlouisfed.org/series/JHGDPBRINDX

All history is now the default history selection for all four charts in a new
session. A user's explicit selection remains active within that session.

The indicator uses the same dark styling, latest observation cards, historical
recession shading, history controls, static and interactive charts, CSV export,
refresh, and saved-snapshot fallback as the existing charts. Quarterly dates
remain quarterly; missing quarters are not filled with invented observations.

The probability axis runs from 0 to 100%, with dashed entry (>67%) and exit
(<33%, after entry) thresholds. The explanation distinguishes the lagged GDP
assessment from a future recession forecast or an official NBER declaration.
The estimate is for the quarter before the newest available GDP quarter;
published index values are not subsequently revised, according to the source.
FRED's metadata labels units percentage points; its notes describe percent probability.

The scheduled macro snapshot refresh now includes this series. Existing
FRED_API_KEY configuration is reused. Deploy, then select Refresh recession data;
run Refresh macro snapshots in GitHub Actions to save its first durable snapshot.
No synthetic data or new credentials are included. This package has not been
deployed by the assistant. Automated tests use fixtures rather than a live API key.
