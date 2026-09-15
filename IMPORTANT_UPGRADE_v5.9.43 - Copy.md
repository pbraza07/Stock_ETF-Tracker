# MarketScope v5.9.43

## Top 200 four-stock combo rankings — 5Y and 10Y

Portfolio Split Simulator replaces the prior two Top 50 10Y dropdowns with four Top 200 selectors:

- 5Y Best Profit
- 5Y Best Worst Year
- 10Y Best Profit
- 10Y Best Worst Year

Every combination contains exactly four stocks from four different sectors. Rankings use a normalized $100,000 starting portfolio with a 25% initial allocation per stock. Selecting a preset automatically loads the four symbols into Portfolio Simulator and chooses the matching 5Y or 10Y horizon with Equal split.

## Saved Portfolio/PDF upgrade protection remains active

The following are protected live-user-data paths and are not shipped/overwritten by this release:

- `data/saved_portfolio_simulations.json`
- `data/generated_pdfs/`

Keep `MARKETSCOPE_GITHUB_TOKEN` configured in Render so saved Portfolio Simulation records and PDF artifacts remain durable across redeployments.
