# MarketScope v5.9.31

## Portfolio common-history guard

- Portfolio Simulator now determines the newest contiguous completed-year history available for every selected instrument.
- Historical horizon choices are limited to that common history, preventing simulations from requesting years before a stock IPO or ETF inception.
- If a previously selected horizon becomes invalid after changing instruments, MarketScope automatically adjusts it to the longest valid common horizon (or YTD if no completed year is shared).
- The UI identifies the instrument(s) limiting the common history.
- Individual return-period/year tiles with no saved return are disabled instead of behaving as valid simulation inputs.
- Existing Sector Performance duplicate-column and drill-down fixes from v5.9.30 are preserved.
