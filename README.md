# MarketScope v5.7 — Annual Returns + Investment Simulator

MarketScope tracks Nasdaq-screened stocks with market capitalization strictly above **$100B** plus the preserved **213-ETF CSV universe**.

## What changed in v5.7

- Replaced the displayed 1Y–10Y CAGR ladder with **actual completed calendar-year returns**.
- During 2026, cards display **2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016**. The labels roll forward automatically in future years.
- Short-horizon fields remain **1D, 1M, 3M, 6M, YTD**.
- Every annual number is the actual adjusted return for that calendar year, not an average and not CAGR.
- Added a global **Investment amount ($)** field. Each stock/ETF card estimates what that amount would be worth after compounding the available completed annual returns in chronological order.
- **Include current YTD** is on by default, so the calculator can extend the completed-year simulation through the current date using the YTD return.
- The selected-instrument detail panel also shows starting investment, estimated value, profit/loss, and total compounded return.
- Cards remain sortable by Market Cap, Rating, every short-horizon return, and every displayed calendar year.
- The daily refresh remains **6:00 PM America/New_York** and now downloads `max` adjusted history so ten complete calendar years can be calculated correctly.

## Return order inside each card

**1D → 1M → 3M → 6M → YTD → latest completed year → ... → tenth completed year**

Example during 2026:

**1D → 1M → 3M → 6M → YTD → 2025 → 2024 → 2023 → 2022 → 2021 → 2020 → 2019 → 2018 → 2017 → 2016**

## Data

- Stock universe and analyst consensus: Nasdaq Stock Screener
- Market history: Yahoo Finance via `yfinance`, `auto_adjust=True`
- ETF universe: exactly 213 symbols from `data/etf_allowlist.csv`
- Durable snapshot: GitHub-generated `data/market_snapshot.csv`

## First refresh after upgrade

Run the GitHub Action once after deploying v5.7. The old CAGR fields are deliberately **not converted** into annual returns. MarketScope waits for real historical data and calculates each year correctly.

MarketScope is informational and is not investment advice.
