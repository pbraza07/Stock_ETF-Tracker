# MarketScope v5.9.5 - Saved Portfolio Simulation PDF Library

This release adds a durable in-app library for Portfolio Split Simulator results.

## New workflow
- Complete a Portfolio Split Simulator calculation.
- Give the simulation an optional name.
- Click **Save PDF to Library**.
- Open **Saved Simulations** inside MarketScope to see every saved simulation.
- Each saved simulation shows the original period, instruments, allocation, starting value, ending value, profit/loss, and total return.
- Click **Download PDF** to retrieve the simulation as a PDF.
- Click **Delete** and confirm to remove a simulation no longer needed.

## PDF layout
The generated PDF follows the supplied MarketScope reference: dark futuristic background, green title, four summary KPI panels, and a holdings/allocation result table with green/red profit and return values.

## Persistence
Saved simulations are stored as structured records in `data/saved_portfolio_simulations.json` when created. The upgrade package ships only `data/saved_portfolio_simulations.bootstrap.json`, so future upgrades do not overwrite the user's live simulation library.

When `MARKETSCOPE_GITHUB_TOKEN` is configured, the library is saved durably to the GitHub repository and remains available across Render restarts and devices. Without the token, the current Render process can still save locally, but that local storage is ephemeral.
