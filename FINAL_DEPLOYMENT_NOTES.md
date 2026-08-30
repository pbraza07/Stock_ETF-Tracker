# v5.9.32 deployment notes

Deploy this package as the direct successor to v5.9.31. No new environment variables are required.

Post-deploy smoke test:
1. Open **Portfolio Simulator** and select four instruments where one has materially shorter history.
2. Confirm **1Y through 20Y remain selectable**. Select 20Y and confirm the caption reports the shorter effective common-history window rather than throwing an error.
3. Run the simulation and confirm all selected instruments use the same start/end calendar years. If annual withdrawals are enabled, confirm the withdrawal schedule uses that same effective common window.
4. Open **Sector Performance**. Confirm the old wide `stocks / View top performers` button is gone.
5. Tap the **TOTAL STOCKS · N** control on a sector card. Confirm a popover opens in the current screen.
6. Tap YTD, 1Y, 5Y and 20Y in the popover timeframe selector. Confirm the table re-ranks and **Total Profit** / **Total Profit %** update without duplicate-column errors.

# v5.9.31 deployment notes

Deploy this package as the direct successor to v5.9.29. No new environment variables are required.

Post-deploy smoke test:
1. Open **Sector Performance**.
2. Rank by **YTD** and tap the **Stocks / View top performers** control inside a sector card.
3. Confirm the Top Performers table opens with no duplicate-column error.
4. Repeat with **1Y** as the ranking period.
5. Confirm the old separate button below the sector card is no longer present.


## v5.9.31 portfolio-history safety
- Portfolio period choices are constrained to common contiguous history across selected instruments.
- Pre-IPO/pre-inception years cannot be selected for simulation.
- If a saved period becomes unsupported after changing instruments, the app automatically moves to the longest valid common horizon or YTD.
- Card return tiles without data are disabled.
