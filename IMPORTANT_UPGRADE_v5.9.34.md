# IMPORTANT UPGRADE — MarketScope v5.9.34

## Sector Performance multi-year profit fix

The Sector Performance top-performers table now derives 1Y–20Y returns by compounding the underlying completed calendar-year returns instead of attempting to read nonexistent literal columns such as `6Y`.

- 1D, 1M, 3M, 6M and YTD continue to use direct snapshot return fields.
- 1Y through 20Y compound the most recent N completed calendar-year returns for each stock.
- Total Profit % uses the selected timeframe return.
- Total Profit $ equals the investment basis multiplied by the selected compounded return.
- A multi-year result remains unavailable only when that stock genuinely lacks all required annual-return history.
- The complete 1Y–20Y table is materialized from the same calculation engine used for ranking and profit.
