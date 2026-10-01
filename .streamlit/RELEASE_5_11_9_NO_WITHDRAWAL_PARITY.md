# MarketScope 5.11.9 corrective fix: no-withdrawal parity

- One canonical Portfolio Information & Performance table schema is used with
  and without withdrawals.
- No-withdrawal mode includes Positive years, Positive months, worst/best year,
  yield/dividend, 1D/1M/3M/6M/YTD and all completed-year returns.
- No-withdrawal portfolio Positive Months is calculated from actual monthly
  return history on the naturally drifting holding balances.
- The value is persisted for saved simulations and repaired for compatible
  legacy records.
- No-withdrawal PDFs retain the same core summary/information/timeframe
  structure as withdrawal PDFs.
- Withdrawal-specific cash-flow pages remain conditional.
- Internal PDF layout contract is advanced to rebuild cached PDFs.
- Application version remains 5.11.9.
