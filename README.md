# MarketScope v5.9.70 — 6-Month Nasdaq Change History

Market Navigator now includes a **6-Month Change History** button beside the manual Nasdaq refresh. MarketScope permanently retains every recorded Nasdaq >$100B stock addition/removal and analyst-rating change in an append-only history file, while the button displays only the most recent six months.

# MarketScope v5.9.69 — Saved Simulation Inline Withdrawal Summary

Saved recurring-income portfolios now show the Yearly or Monthly withdrawal summary **inside the same Saved Simulation card** as Invested / Ending / Profit-Loss / Return. The compact second row sits directly under those primary metrics and uses smaller typography so the saved library is dense and easy to scan.

# MarketScope v5.9.68 - PDF Withdrawal Summary + Market Table Target Transcription

Portfolio PDF page 1 now places the applicable yearly/monthly withdrawal summary directly inside the **TOTAL INVESTED** card. Low / Average-Consensus / High analyst targets displayed in Market Table are also remembered in-session and transcribed into PDF page 1, preventing a second failed Yahoo lookup from turning visible targets back into dashes.

# MarketScope v5.9.67 — Save / Manage Withdrawal Summary

Save / Manage now displays the same annual or monthly withdrawal KPI summary as the live Portfolio Simulator, and Saved Simulations retain that summary beneath each recurring-income record.

# MarketScope v5.9.66 — End-to-End Price Target Fix

Analyst **Low / Average-Consensus / High** targets are now repaired end-to-end across Market Table, Card View, Full Details, Comparison, saved simulations and Portfolio PDF page 1. The Yahoo/yfinance resolver no longer loses its `get_info()` fallback when the analyst-target endpoint throws, target-rich snapshots are preferred over target-empty equivalents, and cached misses receive a direct per-symbol retry.

# MarketScope v5.9.65 — Manual Nasdaq Universe Refresh

Market Navigator now has a dedicated **Refresh Nasdaq Universe Now** button. It refreshes >$100B Nasdaq stock membership, analyst ratings, added/removed symbols, and the universe timestamp immediately. The scheduled workflow also persists universe metadata before the longer Yahoo/history pipeline, preventing later data-job failures from leaving the universe status stuck at Pending.

# MarketScope v5.9.64 - Analyst Price Target Restore

MarketScope now hydrates stock analyst **Low / Average-Consensus / High** price targets through one shared data path used by Card View, Market Table, Comparison, Portfolio Simulator saves, and saved-PDF rebuilds. Older saved PDFs are forced through the v23 enrichment contract so the Portfolio Instrument Snapshot no longer shows target placeholders when Yahoo/yfinance has a valid range.

# MarketScope v5.9.63 — 20Y $160K Annual-Withdrawal Top 250

Portfolio Simulator now includes a **20-year / $300K start / $160K yearly withdrawal / Top 250** ranking family for Rebalanced and Not-Rebalanced strategies. Every portfolio uses four stocks from four different sectors and each ticker is capped at ten appearances across each Top 250 list.

# MarketScope v5.9.62 — Responsive Yearly Withdrawal + Compact Simulator KPIs

Yearly Withdrawal now uses the same responsive five-card visual system as Monthly Withdrawal, including a full RB/NR **Withdrawals Funded** card. The main Portfolio Simulator totals (Portfolio Invested, Ending Value, Profit/Loss, Return) are also responsive compact cards instead of oversized stacked native metrics on mobile.

# MarketScope v5.9.61 — $160K Annual-Withdrawal Top 100

Portfolio Simulator now has a dedicated **$300K start / $160K per year / 10Y** Top-100 family for Rebalanced and Not-Rebalanced portfolios. Every portfolio contains four stocks from four different sectors and each ticker is capped at five appearances across each Top 100 list. Coverage fields make it explicit when an aggressive $160K withdrawal eventually depletes a portfolio.

# MarketScope v5.9.60 — UI Visibility + Card Logo Restore

This release removes an internal monthly-return source-priority message that was accidentally rendered by Streamlit, replaces the monthly-withdrawal KPI row with a responsive no-truncation grid, and restores real company/ETF logos in Card View with a resilient Yahoo/issuer-first fallback chain. Ticker initials remain only as the final image-failure fallback.

# MarketScope v5.9.59 - Monthly PDF Yearly Cash-Flow Reconciliation

The monthly-withdrawal PDF comparison now shows the **true compounded Jan-Dec portfolio return**, actual cash withdrawn during each year, December 31 remaining balance, and **Year-End + Withdrawn** for Rebalanced and Not Rebalanced strategies. The misleading December-only return columns have been removed.

# MarketScope v5.9.58 — Dynamic Lifetime Annual History

MarketScope's annual-return history now expands automatically every year from the fixed **2001** baseline. During 2026 the app shows 25 completed years (2001–2025); during 2027 it automatically becomes 26 years (2001–2026), then 27 years in 2028, with no code change required. The same dynamic horizon drives Market Table, Card View, simulations, withdrawals, comparisons, sectors, charts, verification and Portfolio PDFs.

# MarketScope v5.9.57 - 25Y Withdrawal Source Fix

Withdrawal simulations now use Market Table as the annual-return source of truth. The daily refresh also persists actual monthly returns for the full **2001–2025** window, so monthly Portfolio Simulator withdrawals no longer depend on a separate 10Y-only row being present. Actual monthly returns are reconciled to each displayed annual return; no synthetic annual-to-month conversion is used.

# MarketScope v5.9.56 — Independent Historical Data Verification

MarketScope now automatically cross-checks every comparable 2025–2001 annual return against independent **Stooq U.S. bulk historical data**. Yahoo/yfinance remains the primary adjusted-return source; Stooq is a verification layer only. Differences above **0.25 percentage points** are flagged for review and never silently replace the primary return.

# MarketScope v5.9.55 — 25Y Persistence Race Fix

The automatic 25-year annual-history calculation remains unchanged from v5.9.54, but its durable GitHub persistence is now race-safe. The verified 2025–2001 snapshot is persisted immediately after validation, before slower ranking jobs, and concurrent `main` updates are handled by fetch/reset/reapply/retry logic instead of losing the generated data.

# MarketScope v5.9.54 — Automatic 25-Year Annual History

All 25 completed calendar-year returns are now maintained automatically by the normal MarketScope snapshot refresh. The separate repair banner/button is removed. Historical downloads explicitly begin at 2000-01-01 so 2001 can be calculated from a genuine prior-year anchor, and verified older values are preserved across temporary provider omissions.

# MarketScope v5.9.53 - Verified 25-Year Historical Backfill

MarketScope now validates and repairs the five oldest annual-return years introduced by the 25Y expansion (2005-2001). The app prefers the snapshot with the strongest genuine 25-year history, provides a targeted repair action when needed, and refuses to synthesize pre-inception returns.

# MarketScope v5.9.52 — Recession Top 100 Max-5 Diversification

Recession-Balanced Top 100 rankings now enforce a hard **maximum of five appearances per ticker** in each strategy list while preserving the 2 Profit Engines + 2 Recession Defense + 4 different sectors structure.

# MarketScope v5.9.51 — Compact Ranking Buttons + Recession-Balanced Portfolios

Portfolio Simulator ranking families are now hidden behind separate buttons. A new Recession-Balanced Top 100 provides Rebalanced and Not-Rebalanced four-stock portfolios with two Profit Engine stocks and two historically Recession-Defense stocks, all from different sectors. Detailed Rebalanced/Not-Rebalanced tables now use the same full-field contract as the 10Y $300K / $85K yearly-withdrawal ranking.

# MarketScope v5.9.50 - 25-Year Annual Return Coverage

MarketScope now supports **25 completed calendar years of annual-return history app-wide**. In 2026 that means 2025 through 2001 where genuine adjusted-price history exists. Investment/portfolio/sector horizon controls now run from **1Y through 25Y**, while the existing 5Y/10Y ranked-combination products retain their intended ranking windows.

## MarketScope v5.9.40

Portfolio Simulator PDFs include Rebalanced vs Not-Rebalanced annual withdrawal results, side-by-side yearly balances, and detailed schedules for both strategies.

# MarketScope v5.9.38

## v5.9.38 — Rebalanced vs Not-Rebalanced Annual Withdrawals

When annual withdrawals are enabled, Portfolio Simulator now calculates both annual-rebalanced and natural-weight-drift (not rebalanced) paths, shows both year-by-year tables plus a side-by-side comparison, and persists both schedules with saved simulations.

## v5.9.37 — Remove PDF Setup + Explicit Timeframe-Year Labels

Sector Performance now compounds completed calendar-year returns for 1Y–20Y selections so Total Profit and Total Profit % populate correctly for multi-year rankings. Short-period metrics continue to use direct snapshot returns.


## v5.9.33 — Sector Performance Scalar Fix + Print PDF Removal

- Portfolio Simulator keeps **YTD and every 1Y–20Y option available**. If one or more selected instruments did not exist for the full requested horizon, MarketScope uses only the newest completed calendar years shared by every selected instrument, so the effective simulation begins when the full selected portfolio has valid history.
- Portfolio result cards disclose the requested horizon and effective common-history years when the full requested span is unavailable. Annual-withdrawal schedules use the same common-year window.
- Sector Performance removes the old **stocks / View top performers** button. The **TOTAL STOCKS** KPI is now the drill-down control.
- Tapping **TOTAL STOCKS** opens an in-screen Streamlit popover containing every tracked stock in that sector, ranked by a clickable timeframe selector.
- The sector stock table shows **Total Profit ($), Total Profit (%), 1D, 1M, 3M, 6M, YTD, 1Y through 20Y**, plus logo, name, rating, current price, average target and market cap. Selecting a timeframe re-ranks the stocks and recalculates Total Profit and Total Profit % from the chosen investment basis.

Portfolio Simulator now limits historical horizons to the contiguous completed-year history shared by every selected instrument. Unsupported pre-IPO/pre-inception years are excluded automatically, invalid retained horizons are adjusted safely, and missing individual year tiles are disabled. The v5.9.30 Sector Drill-Down Button + Duplicate Column Fix remains included.

## v5.9.30 — Sector Drill-Down Button + Duplicate Column Fix

- Fixes the Sector Performance Top Performers crash caused when the selected ranking period (for example YTD or 1Y) duplicated a fixed table column.
- De-duplicates the drill-down dataframe column list before passing it to Streamlit/PyArrow.
- Moves the Top Performers action into the sector card's **Stocks** KPI. The stock-count control itself now opens/closes the sector drill-down.
- Removes the redundant separate **View top performers** button below each sector card.
- Preserves stock logos, current price, analyst rating, target upside, selected-period return, YTD, 1Y and market-cap details in the Top Performers panel.


## v5.9.29 — Sector Top Performers Logo Fix

Sector Performance top-performer drill-down now uses the same cached logo resolver as the rest of MarketScope, eliminating the runtime NameError while preserving logo display and top-performer ranking behavior.


Portfolio Simulator now includes an optional **Annual withdrawals** toggle and yearly cash-withdrawal amount. For 1Y–20Y simulations, MarketScope applies each selected instrument's actual saved calendar-year return from oldest to newest, removes the requested cash withdrawal proportionally after each completed year, and displays a year-by-year balance schedule with starting balance, combined return, gain/loss, balance before withdrawal, withdrawal amount, and remaining invested balance. Saved simulations persist the schedule and include it in the PDF.

## v5.9.27 — Ranked 4-stock 10Y portfolio combinations

- Adds a collapsible **Top 4-Stock Combos (10Y)** workspace inside Portfolio Simulator.
- Two side-by-side dropdowns expose **Top 50 Best Profit Generator** and **Top 50 Best Worst Year** combinations.
- Every combination contains exactly four stocks from four different sectors. Each Top 50 list contains **10 semiconductor-containing combinations and 40 without semiconductor stocks**.
- Rankings use the packaged user-supplied stock export and the ten completed calendar years **2025 through 2016**.
- Profit ranking matches the Portfolio Simulator: a $100,000 benchmark starts at 25% per stock; each stock compounds its own ten annual returns and the four ending values are summed.
- Best-worst-year ranking maximizes the weakest equal-weight combined calendar-year return across the same ten years, using 10Y total profit as the secondary tie-breaker.
- Selecting a ranked combo automatically loads all four symbols into the Portfolio Simulator and switches it to **10Y / Equal split**.
- Both rankings include a full table with all ten annual combination returns, worst year, ending value, total profit, total return, and 10Y CAGR.

## v5.9.24 — Comparison selection state fix

The Stock & ETF Comparison selector now commits selections before rerun and no longer resets new mobile/desktop choices to stale state. Selected instruments immediately render cards, table, Yahoo/company logos and all comparison metrics.

## v5.9.22 — PDF first-page market data + comparison logos

- All portfolio PDFs place instrument name, sector, analyst rating, current price, low target, average/consensus target and high target on page 1.
- Older saved PDFs are rebuilt to the new page-1 contract when opened from the library.
- Selected Stock & ETF Comparison cards and the comparison table now show instrument logos retrieved from Yahoo/company metadata when available, with a ticker fallback.
- Mobile Share PDF and Back to MarketScope controls are preserved.





## v5.9.21 — Single comparison selector + PDF price/target snapshot

- The **Stocks & ETFs to compare** searchable multiselect is now the only place that adds or removes comparison instruments.
- Removed the separate Enhanced Stock & ETF Search box and removed Card/Table add-to-comparison entry points to avoid duplicate workflows on mobile.
- Selector labels include ticker, name, type and sector so the native multiselect search remains useful.
- Saved Portfolio Split Simulator PDFs now persist and display each instrument's **current price** alongside analyst **low / average / high targets**.
- Existing mobile PDF viewer remains the supported sharing surface with **Share PDF** and **Back to MarketScope** controls.


## v5.9.20 — Organized top tabs + enhanced comparison search

- Adds top-level workspaces for **Market Navigator**, **Portfolio Simulator**, **Stock & ETF Comparison**, and **Alerts & Help**.
- Market Navigator groups Quick Filters, Investment Simulator, Card View, Table View and market refresh controls.
- Portfolio Simulator opens directly into **Build Simulation** and **Saved / Manage** internal tabs, preserving PDF persistence, native mobile sharing, download and delete controls.
- Stock & ETF Comparison adds enhanced search across symbol, name, type, sector, industry and analyst rating, plus optional Yahoo Finance discovery for instruments outside the tracked universe.
- Adds a compact **PDF / GitHub Setup** popover that explains `MARKETSCOPE_GITHUB_TOKEN` without exposing its value and reports whether the secret is configured.
- Preserves v5.9.19 server-side PDF storage and mobile Share PDF / Back to MarketScope functionality.

## v5.9.19 — Server PDF persistence + phone sharing

- Based strictly on the authoritative v5.9.18 baseline.
- Saved simulation PDFs are persisted as actual server files in `static/generated_pdfs/`.
- With `MARKETSCOPE_GITHUB_TOKEN`, PDF artifacts are also backed up durably to `data/generated_pdfs/` in GitHub and can be restored after a Render restart/redeploy.
- Optional mounted-disk mirror: `MARKETSCOPE_PDF_PERSIST_DIR`.
- Saved Simulations adds **Open / Share PDF**, using a mobile-first PDF viewer with native iOS/Android share-sheet support and a **Back to MarketScope** control.
- Existing v5.9.18 saved records are migrated automatically when their PDF is first opened.

## v5.9.18 — Nasdaq universe audit + 2Y daily card charts + PDF first-page analyst snapshot

- Shows **Nasdaq Universe Last Refreshed** and **Stocks Added / Removed Today** from a persisted universe membership metadata file.
- Adds a compact **2-year chart using 1-day adjusted bars** to each visible Stock/ETF card. The page fetch is batched and cached for 30 minutes.
- Keeps the **v5.9.7 compact three-column return tile layout on mobile**, while every tile remains clickable for exact-period profit/loss.
- Portfolio Split Simulator now starts at **$100,000** by default.
- New saved simulations retain **instrument name, sector, analyst rating, and analyst Low / Average / High price targets**.
- PDF page 1 shows those instrument fields; combined timeframe performance moves to page 2 to keep the first page readable.


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

## v5.9.24
Comparison cards now mirror Market Navigator Card View functionality while preserving logos. Nasdaq universe refresh metadata also records and displays analyst-rating transitions for retained stocks.

## v5.9.26
- Comparison mini charts now load from the comparison selection itself.
- Market Navigator stock/ETF cards display instrument logos when Yahoo/company metadata provides one.
- New Stock Sector Performance top tab aggregates stocks-only performance across every MarketScope timeframe with equal-weight or market-cap-weighted calculations.


### v5.9.46 monthly portfolio income simulation
Portfolio Simulator supports separate Yearly withdrawal and Monthly withdrawal modes. The monthly mode can load Top 100 four-stock, four-sector presets for a $300,000 start and $5,000 monthly cash flow over the 2016-2025 completed-year window, with HWM excluded. Every modeled month uses the actual adjusted month-end return calculated from Yahoo/yfinance daily market history. Saved PDFs include all monthly rows for both rebalanced and non-rebalanced paths.

## v5.9.48 - PDF version + Positive Months

Portfolio Simulator PDFs now show the active MarketScope version on page 1. Portfolio Simulator tables also show positive-month counts calculated from actual adjusted month-end returns. Monthly Top 100 ranking files persist `Positive Months` after the next scheduled refresh, while older actual-monthly ranking files are enriched on display for compatibility.

## v5.9.49 - Positive Months repair

Portfolio Simulator monthly withdrawal results now persist the actual portfolio positive-month count instead of allowing a missing field to display as zero. Monthly Top 100 tables show Positive Months prominently as `count/months funded`, and Portfolio Simulator PDFs show positive-month counts on page 1, on the monthly strategy-comparison page, and in the instrument analytics table. Existing v5.9.48 saved monthly schedules are repaired during PDF rebuild.
