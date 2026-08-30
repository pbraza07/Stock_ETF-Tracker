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
