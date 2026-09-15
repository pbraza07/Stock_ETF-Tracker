# MarketScope v5.9.48

## PDF page 1 now shows the MarketScope version

Every newly generated Portfolio Simulator PDF now displays the active MarketScope release in the upper-right corner of page 1, for example:

`MarketScope v5.9.48`

The saved simulation record also stores the app version used for the PDF. The Portfolio PDF layout contract is now v11, so older saved PDFs are rebuilt into the new first-page format when opened.

## Positive Months in Portfolio Simulator tables

MarketScope now exposes actual positive-month counts based on adjusted month-end market returns:

- Portfolio Information & Performance Table: adds `Positive months` for each selected instrument, shown as positive months / available months in the active completed-year simulation window (up to 120 months).
- Monthly Top 100 Rebalanced / Not Rebalanced tables: adds `Positive Months` for each four-stock portfolio combination.
- Monthly withdrawal result summary: shows positive-month counts for Rebalanced and Not Rebalanced portfolio paths.
- Portfolio Simulator PDF monthly strategy comparison: records the positive-month counts for both strategies.

A month is positive only when the portfolio's actual market return for that month is greater than 0%, before the month-end withdrawal is taken.

## Compatibility

If the currently stored actual-monthly Top 100 ranking files were generated before v5.9.48 and do not yet contain the new `Positive Months` field, the app calculates that field from the durable actual-monthly return dataset at display time. The scheduled ranking generator also writes the field permanently on the next refresh.

## Persistence protection

The v5.9.40+ saved simulation/PDF protections remain unchanged. Do not overwrite or delete:

- `data/saved_portfolio_simulations.json`
- `data/generated_pdfs/`
