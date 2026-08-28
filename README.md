# MarketScope v5.8.1 — Navigation & Chart UX Upgrade

MarketScope tracks Nasdaq-screened stocks with market capitalization strictly above **$100B** plus the preserved **213-ETF CSV universe**.

## New in v5.8.1

- **Sort Cards By** is now a single button. Sort choices and High/Low direction controls stay hidden until the button is opened.
- ETF cards use the ETF **Sector** field as the descriptive card name, while stock cards continue to use the company name.
- Clicking **Open SYMBOL** immediately loads that instrument's yearly chart and then scrolls the browser to the chart section.
- The instrument performance matrix uses a responsive grid so its values remain in source order on phones.
- The year selector remains ordered newest-to-oldest (`current year → 10 years back`) and wraps into an ordered mobile-friendly layout.
- The existing 213-ETF CSV universe is preserved.

## Preserved from v5.8

- Added a **News** button to every stock/ETF card. News is fetched on demand so the main dashboard stays fast.
- The News panel shows up to **3 recent directional fundamental stories** from the latest 7 days.
- Each story shows a green **▲ UP DRIVER** or red **▼ DOWN DRIVER**, headline, publisher/time, identified driver, and a directional-read disclaimer.
- Neutral or ambiguous headlines are not forced into an UP/DOWN label.
- Added **Investment years** buttons for **1Y through 10Y**.
- The investment simulator now compounds exactly the number of selected completed calendar years. If an instrument does not have the full selected history, MarketScope shows it as unavailable instead of silently shortening the period.
- **Total Profit ($)** sorting now uses the selected investment amount, selected investment years, and the Include current YTD setting.
- The instrument detail view now includes a **Chart year** selector for the current year plus the prior 10 calendar years.
- Selecting a different chart year replaces the plotted adjusted-close history and year summary metrics for that year.

## Performance fields inside each card

**1D → 1M → 3M → 6M → YTD → 2025 → 2024 → 2023 → 2022 → 2021 → 2020 → 2019 → 2018 → 2017 → 2016**

The year labels roll forward automatically. Completed calendar-year values are actual annual adjusted returns, not CAGR.

## News Impact methodology

The app retrieves recent Yahoo Finance news through `yfinance` only when a News button is opened. It filters for the selected symbol when related-ticker metadata is available, then applies a transparent rule-based classifier to fundamental language such as earnings beats/misses, guidance raises/cuts, upgrades/downgrades, approvals, contracts, legal/regulatory risks, recalls, dilution and similar catalysts.

The arrows are **directional context, not a prediction**. A green arrow means the detected fundamental language is favorable; a red arrow means it is unfavorable. Market prices can move differently for many reasons.

## Investment simulator

1. Enter an investment amount.
2. Choose **1Y–10Y**.
3. Choose whether to include the current YTD return.
4. Each card shows ending value, dollar profit/loss and compounded percentage return.
5. Sort by **Total Profit ($)** to rank the cards using those exact settings.

No future returns are assumed. Taxes, fees, deposits and withdrawals are excluded.

## Year-by-year chart

Open any card and choose the current year or one of the prior 10 years. MarketScope loads the symbol's max adjusted history once, filters it to the selected calendar year and displays:

- selected-year return / YTD
- year-start adjusted close
- latest/year-end adjusted close
- high close
- low close
- daily adjusted-close chart

## Data

- Stock universe and analyst consensus: Nasdaq Stock Screener
- Market history and on-demand news: Yahoo Finance via `yfinance`
- ETF universe: exactly **213 symbols** from `data/etf_allowlist.csv`
- Durable snapshot: GitHub-generated `data/market_snapshot.csv`
- Daily refresh: **6:00 PM America/New_York**

MarketScope is informational and is not investment advice.
