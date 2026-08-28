# MarketScope v5.7 Return Methodology

## Adjusted history
MarketScope uses Yahoo Finance daily history through `yfinance` with `auto_adjust=True`. This incorporates split/dividend adjustments into the historical price series used for return calculations.

## Short-horizon returns
The following are point-to-point adjusted returns:

- 1D
- 1M
- 3M
- 6M
- YTD

Formula:

`Return = (Ending Adjusted Price / Starting Adjusted Price) - 1`

## Ten completed calendar-year returns
MarketScope no longer displays 1Y–10Y CAGR fields.

For each completed calendar year `Y`:

`Annual Return(Y) = (Adjusted Close at end of Y / Adjusted Close at end of Y-1) - 1`

The app uses the final valid adjusted trading close near December 31 for each year. If the required prior-year anchor is unavailable—for example because the instrument IPO'd during that year—the annual return is shown as unavailable rather than fabricated.

The current incomplete calendar year is shown separately as **YTD**. During 2026, the ten completed annual labels are 2025 through 2016.

## Investment simulator
The user enters a dollar principal. For each instrument, MarketScope uses the most recent contiguous sequence of available completed annual returns and compounds them oldest-to-newest:

`Value_next = Value_current × (1 + Annual Return)`

If **Include current YTD** is enabled, the YTD return is applied after the completed annual returns to estimate value through the current date.

The simulator assumes:

- one lump-sum starting investment,
- no additional deposits or withdrawals,
- no taxes, commissions, spreads, or management fees beyond what is already reflected in adjusted market history,
- no forecasted/future return.

It reports historical scenario value, not a guarantee of future performance.
