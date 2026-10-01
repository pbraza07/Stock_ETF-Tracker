# MarketScope v5.9.27 — Top 4-Stock 10Y Combo Rankings

Built from v5.9.26.

## New Portfolio Simulator workflow

Open **Portfolio Simulator → Build Simulation → Top 4-Stock Combos (10Y)**.

Two ranked selectors are available:

1. **Top 50 — Best Profit Generator**
2. **Top 50 — Best Worst Year**

Each list contains 50 four-stock combinations with four different sectors: exactly 10 combinations include a semiconductor stock and 40 exclude semiconductor stocks.

The packaged source is `data/portfolio_combo_source_2026-08-29.csv`. Ranked outputs are `data/top50_profit_generators_10y.csv` and `data/top50_best_worst_year_10y.csv`.

Selecting a combo automatically loads the four stocks into the Portfolio Simulator and sets the simulator to **10Y** and **Equal split**.

## Ranking methodology

- Completed calendar years: 2025–2016.
- Benchmark starting value: $100,000, $25,000 per stock.
- Profit ranking: each stock compounds its own ten annual returns exactly as MarketScope's Portfolio Split Simulator does; the four ending values are summed.
- Annual portfolio rows: equal 25% weighted average of the four stock annual returns.
- Best worst-year ranking: highest minimum annual portfolio return over the ten completed years; total profit is the secondary ranking criterion.
