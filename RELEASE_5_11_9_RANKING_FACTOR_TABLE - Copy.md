# MarketScope v5.11.9 — Ranking Factor Table Audit Patch

This corrective patch keeps the current MarketScope version at **5.11.9** and
extends both Top 12 result tables so the user can see the data that actually
drives the ranking.

## Recession table

The primary table now includes:

- Final Recession Score
- Defense Score (30%)
- Drawdown Score (20%)
- Recovery Score (15%)
- Bear Model Score (15%)
- Consistency Score (10%)
- Current Strength Score (5%)
- Profitability Score (5%)
- Shared Risk Penalty
- Recession Additional Penalty
- Worst Stress Return %
- Maximum Drawdown %
- Recovery Time and basis
- Bear P10 and Bear P25 modeled annualized returns
- Positive Years %
- Historical CAGR %
- Data Confidence
- Why Selected

## Max-Profit table

The primary table now includes:

- Final Max-Profit Score
- Historical Performance (25%)
- Recent Performance (15%)
- Future P50 Score (20%)
- Future P75 Score (15%)
- Fundamentals Score (10%)
- Consistency Score (5%)
- Relative Strength Score (5%)
- Downside Quality Score (5%)
- Shared Risk Penalty
- 3Y / 5Y / 10Y CAGR
- P10 / P25 / P50 / P75 modeled annualized returns
- Positive Years %
- Maximum Drawdown %
- Data Confidence
- Why Selected

## JSON history schema

New ranking runs persist the factor scores and supporting evidence inside the
existing `data/top12_recession_history.json` and
`data/top12_max_profit_history.json` ledgers.

Older JSON runs remain readable. If the latest saved run predates this schema,
MarketScope displays the saved basic ranking and clearly asks the user to run
Advanced recalculation once. That recalculation creates a new auditable run
without deleting old history.

## Ranking logic

No ranking formula, weight, simulation engine, sector cap, replacement threshold,
historical simulator, or Future Projection calculation is changed by this patch.
