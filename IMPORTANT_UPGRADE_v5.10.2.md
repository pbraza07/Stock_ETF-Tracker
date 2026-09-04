# MarketScope v5.10.2 — Central Projection Percentiles

This release extends **Future Projection** with exact **P25, P50, and P75** Monte Carlo outputs while preserving all v5.10.1 simulation logic and the existing P5/P10/P90/P95 results.

## Added

- P25 Ending Balance
- P50 Ending Balance — the same statistical point as the existing median
- P75 Ending Balance
- P25 / P50 / P75 Total Wealth Profit
- P25 / P50 / P75 Profit % in the detailed projection output
- A user-friendly **Profit %** summary value that defaults to the P50/median scenario
- P25/P50/P75 values in the annual/monthly projection result rows
- P25/P50/P75 Ending Balance plus Profit % summary cards in the Future Projection UI

## Profit % definition

MarketScope v5.10.2 defines projected Profit % path-by-path as:

`(Ending Balance + Withdrawals Received - Contributions - Starting Investment) / Starting Investment × 100`

This is designed for withdrawal-oriented portfolio projections: withdrawals already received remain part of the economic result, while additional contributions are not misclassified as investment profit.

## Compatibility

- Existing P5/P10/P90/P95 outputs remain available.
- Existing `Median Ending Balance` remains for backward compatibility; `P50 Ending Balance` is the explicitly labeled equivalent.
- Existing historical portfolio simulators and withdrawal calculations are unchanged.
- Existing Future Projection inputs, simulation count, random seed, scenario generation, rebalancing, withdrawals, fees, contributions, depletion logic, PDFs, Excel, and CSV export paths are preserved.
- No new environment variables or database/data migration are required.
