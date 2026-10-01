# MarketScope v5.11.42 — Requested earnings iframe parameters

The existing Show Earnings Calendar button now opens the requested parameterized
Investing.com earnings iframe in the same dashboard location. Back to Economic
Calendar restores the original economic widget. Both frames use 520px inner
height, 525px component height, full width and the same dark CSS filter.

Earnings requests the economic widget parameters unchanged except importance=2,3.
The earnings endpoint remains Investing.com's full webpage, not a verified compact
earnings widget. Provider support for these parameters is unverified: week,
country, importance and columns may be ignored. The UI explicitly warns users to
check/select filters within the provider page. The CSS filter changes appearance
but cannot remove provider navigation or change the cross-origin document layout.
No claims of verified live rendering or automatic filtering are made.

Regression tests validate URL parameters, escaping, dimensions, calendar switching
and existing application functionality. No financial calculations are modified.
This is a cumulative source package and has not been deployed.

Validation: 711 regression tests passed (72 warnings).
