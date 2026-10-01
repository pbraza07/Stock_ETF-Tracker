# MarketScope v5.9.45

## Monthly withdrawal portfolios under Portfolio Simulator

This release adds two new 10-year Top 100 preset lists using the same spreadsheet source packaged in MarketScope:

- **Top 100 - Rebalanced Monthly**
- **Top 100 - Not Rebalanced Monthly**

Ranking constraints:

- $300,000 starting portfolio
- exactly four stocks
- four different sectors
- equal 25% starting allocation
- HWM excluded
- $5,000 withdrawal every month
- 120 full monthly withdrawals across completed years 2016-2025
- any combination that cannot fund all 120 withdrawals is excluded
- ranked by remaining balance after month 120

### Important monthly-return methodology

The source spreadsheet contains completed **annual** calendar-year returns, not monthly historical prices. Therefore each stock/year is converted to an equivalent constant monthly return:

`monthly factor = (1 + annual return)^(1/12)`

This preserves that stock's full-year compounded return while allowing a $5,000 cash withdrawal to be modeled each month. It is **not** a reconstruction of the actual sequence of historical monthly prices.

### Portfolio Simulator controls

The previous annual toggle is now labeled **Yearly withdrawal**. A new mutually exclusive **Monthly withdrawal** toggle and monthly dollar input are beside it.

### PDF

Saved Portfolio Simulator PDFs now use layout v9. A monthly-withdrawal simulation includes:

1. Monthly strategy comparison
2. 10-year year-end summary
3. Every monthly row for Rebalanced Monthly
4. Every monthly row for Not Rebalanced Monthly

For a 10-year simulation this is the complete 120-month path for each strategy.

### Persistence

Saved Portfolio simulations and PDFs remain protected across upgrades. Do not overwrite `data/saved_portfolio_simulations.json` or `data/generated_pdfs/`, and keep `MARKETSCOPE_GITHUB_TOKEN` configured in Render.
