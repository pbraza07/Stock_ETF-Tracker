# MarketScope v5.9.1 — ETF Card Render Fix + Stock Sector Labels

MarketScope tracks Nasdaq-screened stocks with market capitalization strictly above **$100B** plus the preserved **213-ETF CSV universe**.

## New in v5.9

- **Live intraday chart on Open Instrument.** Opening a stock or ETF loads a Yahoo Finance/yfinance intraday chart for that one instrument. It uses 1-minute bars when available, falls back to 5-minute bars when necessary, and refreshes approximately every **60 seconds** while the instrument remains open.
- **No paid market-data API is required.** The live panel uses the existing free Yahoo Finance/yfinance data path. Exchange/Yahoo delays can apply, so the chart is near-real-time rather than exchange-direct tick data.
- **Stock analyst price targets inside every stock card:** **Low / Average / High**. The card also shows the implied move from current price to the average target when both values are available.
- Price targets are refreshed during the scheduled GitHub snapshot and manual refresh. Upgrade-safe lazy loading fills targets for the visible stock cards when an older persisted snapshot does not yet contain v5.9 target columns.
- ETFs do not show stock-style price targets because comparable analyst Low/Average/High target ranges are not consistently available for funds.
- The opened instrument detail view repeats Low / Average / High targets plus the implied move to the average target.

## Preserved from v5.8.1

- **Sort Cards By** stays collapsed behind one button until opened.
- ETF card descriptive names use the ETF **Sector** field.
- Open Instrument scrolls directly to the chart area.
- Current year plus prior 10 individual years remain selectable in the historical chart.
- News Impact button with up to 3 recent directional fundamental stories.
- Investment amount and selectable **1Y–10Y** historical investment horizons.
- **Total Profit ($)** card sorting based on the selected investment amount and horizon.
- Actual calendar-year returns rather than CAGR.
- Nasdaq stock universe >$100B only and exactly 213 ETFs.

## Card performance fields

**1D → 1M → 3M → 6M → YTD → previous completed year → ... → 10 completed calendar years**

The year labels roll forward automatically. Completed calendar-year values are actual adjusted calendar-year returns, not CAGR.

## Live chart behavior

1. Click **Open SYMBOL**.
2. MarketScope selects that instrument and scrolls to the chart area.
3. The **Live intraday chart** requests only that symbol from Yahoo Finance.
4. 1-minute intraday bars are displayed when Yahoo makes them available.
5. The live fragment refreshes about every 60 seconds while open.
6. The existing **Year-by-year historical chart** remains directly below it.

## Analyst target methodology

MarketScope reads the Yahoo/yfinance analyst price-target range when available:

- **Low** — lowest current analyst target in the Yahoo range.
- **Average** — mean analyst target.
- **High** — highest current analyst target in the Yahoo range.

Targets are analyst estimates, not guaranteed future prices. Missing coverage is displayed as `—`; MarketScope does not invent a target.

## Data

- Stock universe and analyst rating: Nasdaq Stock Screener
- Adjusted market history, intraday chart, news and stock price-target data: Yahoo Finance via `yfinance`
- ETF universe: exactly **213 symbols** from `data/etf_allowlist.csv`
- Durable snapshot: GitHub-generated `data/market_snapshot.csv`
- Daily refresh: **6:00 PM America/New_York**

MarketScope is informational and is not investment advice.

## v5.9.1 UI patch
ETF cards are rendered as a single compact HTML block to prevent raw HTML from appearing when stock-only price targets are absent. Stock cards now display their sector directly beneath the company name.


## v5.9.2
ETF cards now have an on-demand Top Holdings button backed by Yahoo Finance/yfinance. The app shows Top 10 when available, otherwise Top 5 (or the smaller returned set when Yahoo exposes fewer than five). Card pagination is duplicated at the bottom of the card grid for easier phone and desktop navigation.


## v5.9.3 — Profit & portfolio simulation
- Return tiles in each card are clickable for exact-period dollar profit calculations.
- YTD is available as a standalone investment period.
- Portfolio Split Simulator defaults to $200,000 and supports equal or custom percentage splits across multiple stocks/ETFs, with YTD or 1Y–10Y historical horizons.

## v5.9.4 — Card / Table View tabs

- Adds an app-level **Card View / Table View** tab switch.
- Card View preserves the full futuristic card experience, card sorting, profit clicks, ETF holdings, News, pagination, live chart and instrument intelligence.
- Table View shows every instrument that passes the same active filters in one sortable table.
- Table columns include symbol/name/type/sector/industry, price, market cap, analyst rating, stock price-target low/average/high and average-target implied move, buy-signal flags, 1D/1M/3M/6M/YTD plus ten labeled calendar-year returns, and the current investment simulation ending value/profit/return.
- Table sorting works through explicit Sort Table controls and by clicking any column header.
- Previously removed metadata fields remain hidden by design.
