# MarketScope Return & Signal Methodology — v5.4

Historical market returns use Yahoo Finance through yfinance with adjusted daily prices. Adjusted history accounts for split/dividend adjustments provided by the source.

## Displayed return columns

- `1D`: latest adjusted close versus previous trading close.
- `1M`: point-to-point adjusted total return.
- `3M`: point-to-point adjusted total return.
- `6M`: point-to-point adjusted total return.
- `YTD`: adjusted total return from the prior year-end trading close.
- `1Y Avg`: annualized 1-year return (CAGR over the available near-one-year anchor).
- `3Y Avg`: annualized 3-year CAGR.
- `5Y Avg`: annualized 5-year CAGR.
- `10Y Avg`: annualized 10-year CAGR.

The table does not display Inception Date or Exchange in v5.4.

## Buy signals

`Short Buy` is a rule-based technical screen using SMA20, SMA50, MACD, RSI14, 1M momentum and 3M momentum.

`Long Buy` uses long-trend technical conditions including SMA50/SMA200 and positive medium/long horizon returns. For stocks, Nasdaq Buy/Strong Buy analyst consensus is used as confirmation, and Nasdaq Strong Buy is treated as a fundamental/consensus buy signal. ETFs are technical-only when Nasdaq does not supply a genuine stock-style analyst consensus rating.

`Short Signal New` and `Long Signal New` are true only when a buy signal changes from inactive to active relative to the prior persistent snapshot. This supports alerting without labeling every unchanged active signal as new.

These signals are informational and are not investment advice, a suitability determination, or a guarantee of future returns.
