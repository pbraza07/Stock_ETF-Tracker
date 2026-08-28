# MarketScope v5.8.1 Return Methodology

## Short horizons

- **1D:** latest/live adjusted price versus the prior trading close.
- **1M / 3M / 6M:** point-to-point adjusted market return from the trading price nearest the calendar anchor to the current/latest price.
- **YTD:** current/latest adjusted price versus the final adjusted close before the current calendar year (or the first available trading close of the year when necessary).

## Calendar-year returns

The ten year-labeled fields are **actual completed calendar-year returns, not CAGR**.

For calendar year Y:

`Annual Return(Y) = Adjusted Close(end of Y) / Adjusted Close(end of Y-1) - 1`

A year is left unavailable when the instrument lacks genuine prior-year-end coverage, such as a mid-year IPO.

## Investment simulator

The user chooses an investment amount and **1 through 10 completed years**. MarketScope compounds the exact selected number of most-recent contiguous calendar-year returns in chronological order. If the full selected horizon is unavailable, the simulator reports insufficient history rather than silently using a shorter period.

When **Include current YTD** is enabled, the current YTD return is applied after the selected completed calendar years.

No future returns, recurring deposits, taxes, transaction costs or fees are assumed.

## Year chart

The selected-instrument chart can display the current calendar year plus the prior 10 years. The app filters maximum available adjusted daily history to the selected year, and the chart plus summary metrics update to that year only.

## News Impact

News Impact is separate from return calculations. It is an on-demand, rule-based directional interpretation of recent Yahoo Finance headline/summary language. Green ▲ marks positive fundamental language; red ▼ marks negative fundamental language. Neutral/ambiguous items are not assigned a direction. These labels are informational context, not price forecasts.
