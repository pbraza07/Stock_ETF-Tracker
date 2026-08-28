# MarketScope v5.9.15


## v5.9.17 — 20 completed annual returns

Card View and Table View now expose up to **20 completed calendar-year returns** (2025 through 2006 during 2026), in addition to 1D, 1M, 3M, 6M and YTD. Each annual tile in Card View is clickable and calculates the exact-period profit/loss using the Investment Simulator amount. The 1Y–20Y historical compounding controls and year chart were expanded to match.

**New:** Card View is restored to the v5.9.7 visual organization while every return timeframe is now reliably clickable. Selecting 1D, 1M, 3M, 6M, YTD or any displayed calendar year updates the exact-period dollar profit/loss inside the same card using a card-local Streamlit fragment and pre-rerun state callback.

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
- Current year plus prior 20 individual years remain selectable in the historical chart.
- News Impact button with up to 3 recent directional fundamental stories.
- Investment amount and selectable **1Y–20Y** historical investment horizons.
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
- Portfolio Split Simulator defaults to $200,000 and supports equal or custom percentage splits across multiple stocks/ETFs, with YTD or 1Y–20Y historical horizons.

## v5.9.4 — Card / Table View tabs

- Adds an app-level **Card View / Table View** tab switch.
- Card View preserves the full futuristic card experience, card sorting, profit clicks, ETF holdings, News, pagination, live chart and instrument intelligence.
- Table View shows every instrument that passes the same active filters in one sortable table.
- Table columns include symbol/name/type/sector/industry, price, market cap, analyst rating, stock price-target low/average/high and average-target implied move, buy-signal flags, 1D/1M/3M/6M/YTD plus ten labeled calendar-year returns, and the current investment simulation ending value/profit/return.
- Table sorting works through explicit Sort Table controls and by clicking any column header.
- Previously removed metadata fields remain hidden by design.

## v5.9.5 - Saved Portfolio Simulation PDF Library

Portfolio Split Simulator results can now be named and saved into an in-app library. The PDF layout mirrors the dark MarketScope reference design with four summary KPIs and an instrument allocation/results table. Saved items can be downloaded as PDF or deleted from the library. Durable cross-device storage uses `data/saved_portfolio_simulations.json` through the existing GitHub token persistence pattern; the release package ships only a bootstrap file so upgrades do not erase saved simulations.


## v5.9.6 Portfolio analytics
Completed Portfolio Split simulations now populate a wide analytics table with industry, allocation, 10-year CAGR, positive-year count, best/worst calendar years, trailing regular yield, estimated annual dividend, and every saved timeframe return. Saving the simulation captures this table in the durable record and adds it to the PDF.


## v5.9.7 - Combined portfolio PDF first page
Saved Portfolio Split PDFs now open with a landscape, legible combined portfolio page. It shows 10Y CAGR, positive years, worst/best combined calendar year, allocation-weighted regular yield, total estimated annual dividend, and a single combined return row for 1D, 1M, 3M, 6M, YTD and 2025-2006. Instrument-level allocation, analytics and timeframe tables continue on following pages.


## v5.9.8 - Unlimited Stock Comparison

- Adds a dedicated **Stock Comparison** workspace with no artificial selection limit.
- Add stocks from the new **Compare** button on stock cards, multi-row selection in Table View, or the direct comparison selector.
- Comparison Cards show company, sector, price, market cap, analyst targets, analyst rating, buy signals, every current performance period, and the currently selected investment-simulation result. Cards paginate 12 at a time for browser/mobile performance while the selected comparison list itself remains unlimited.
- Comparison Table shows the full selected stock set in one sortable grid with all current performance periods, analyst targets, signals, and investment-simulation fields.
- ETF cards retain Holdings instead of Compare; this workspace is intentionally stock-only.

## v5.9.9
- Stock & ETF Comparison supports unlimited mixed-instrument comparisons in card and table formats.
- Buy Signal Alerts, Portfolio Split Simulator, and Save / Manage Portfolio Simulations are collapsed behind explicit toggle buttons.
- Investment Simulator is immediately above Display Mode.
- Card period/year profit calculations use fragment-local Streamlit controls so selecting a period updates only that card area without full-page flicker or scroll jumping.


## v5.9.12 — Search in both display modes

- **Card View** now has its own Search stock / ETF field above the card sort/navigation controls.
- **Table View** keeps its Search stock / ETF field beside the table sorting controls.
- Both searches support case-insensitive partial matching across Symbol, Name, Type, Sector, Industry, and Analyst Rating.
- Search is applied before card pagination/table sorting so the result counts and navigation reflect only matching instruments.
- Clearing a view's search field restores that view's full currently-filtered instrument set.


## v5.9.18 - Nasdaq universe audit status + PDF analyst snapshot

The app now records the Nasdaq >$100B universe refresh timestamp and the stocks added/removed during the current U.S. Eastern calendar day. The scheduled workflow commits `data/universe_metadata.json` with the universe and snapshot.

New portfolio PDFs include, on page 1, a compact instrument table with Symbol, Name, Type, Sector, Analyst Rating, Target Low, Target Average and Target High.
