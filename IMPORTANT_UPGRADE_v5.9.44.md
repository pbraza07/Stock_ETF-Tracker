# MarketScope v5.9.44

## New Top 100 withdrawal-survival portfolio rankings

Portfolio Split Simulator now adds two additional 10-year preset rankings generated from `data/portfolio_combo_source_latest.csv`:

- **Top 100 — Rebalanced Annually**
- **Top 100 — Not Rebalanced**

Ranking assumptions:

- Starting portfolio: **$300,000**
- Four stocks exactly, initially **25% each**
- All four stocks must be from **four different sectors**
- Historical period: **2016 through 2025** (10 completed calendar years)
- Annual withdrawal: **$85,000**, taken at the end of each completed year after that year's returns
- A combination qualifies only if it can make the **full $85,000 withdrawal in all 10 years** and still have a balance above $0 after the tenth withdrawal
- Each ranking is ordered by the **remaining portfolio balance after the tenth withdrawal**

### Rebalanced ranking
After each year's returns and $85,000 withdrawal, the remaining balance is reset to the original equal 25% allocation for the next year.

### Not-rebalanced ranking
After each year's returns and proportional $85,000 withdrawal, the remaining holdings keep their naturally drifted weights for the next year.

Selecting either preset automatically loads the four stocks into Portfolio Simulator and sets **$300,000**, **10Y**, **Equal split**, **Annual withdrawals ON**, and **$85,000 per year**.

## Upgrade-safe saved PDFs remain protected

The existing persistent Portfolio Simulation/PDF protections remain unchanged. These live user-data paths are not shipped or overwritten by the release package:

- `data/saved_portfolio_simulations.json`
- `data/generated_pdfs/`

Keep `MARKETSCOPE_GITHUB_TOKEN` configured in Render so saved PDFs remain durable across deployments.
