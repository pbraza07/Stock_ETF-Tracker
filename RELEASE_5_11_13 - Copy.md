# v5.11.13 - YTD simulator

Removes History Check from stock cards and Market Table. Retains independent
verification data and existing PDF audit fields.

Adds Portfolio Simulator > YTD Daily / Weekly / Monthly. Actual adjusted daily
prices drive both equal-weight rebalanced and buy-and-hold simulations. The
withdrawal amount is per chosen cadence, not an annualized amount. Withdrawals
sell holdings proportionally and are capped at remaining assets. Shortfalls
remain visible. Reporting frequency does not alter cash flows. Rebalancing
uses the chosen cash-flow cadence even when withdrawal amount is zero.

Requires a shared prior-year close; newly listed instruments lacking that
baseline cannot be simulated as full YTD. Today's session is excluded. Missing
dates are excluded; no prices or daily returns are fabricated. Final incomplete
weeks/months carry no withdrawal. CSV exports included. Existing historical
and Future Projection calculations are unchanged.

Validation: six targeted YTD accounting tests pass; a mocked-provider Streamlit
test confirms both result tables render. Live-provider and browser
verification have not been performed for this release. Preserve deployed data
when uploading this repository-root overlay.
