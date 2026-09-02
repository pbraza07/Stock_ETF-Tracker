# v5.9.64 deployment note

Deploy over the existing repository. Do not delete live saved Portfolio Simulation JSON/PDF state. After deployment, existing saved PDFs are rebuilt on open against the current market row and the shared target hydrator. The normal scheduled snapshot refresh also persists Low / Average / High target values with lower-concurrency Yahoo retries.

# v5.9.63 deployment note

Deploy over the existing repository. Do not delete live saved Portfolio Simulation JSON/PDF state.

This release adds committed static ranking assets for the new 20Y $160K Top 250 family. Upload those files with the code. They are excluded from the normal market-refresh trigger to avoid workflow recursion.

# v5.9.62 deployment note

Deploy over the existing repository. This is a UI/layout release; no market-data migration is required and live saved Portfolio Simulation JSON/PDF state remains protected. Rebuilt PDFs carry the v21/v5.9.62 layout marker on page 1.

# v5.9.61 deployment note

Deploy this release over the existing repository; do not delete live saved Portfolio Simulation JSON/PDF state.

This release intentionally adds three committed data files under `data/` for the new fixed-source ranking family:
- annual_performance_160k_source.csv
- top100_rebalanced_withdrawal_10y_160k_max5.csv
- top100_not_rebalanced_withdrawal_10y_160k_max5.csv

They are ranking assets, not live user state, and should be uploaded with the code.

# v5.9.60 deployment note

Deploy over the existing repository. No data migration is required.

The app-code change invalidates the old Streamlit logo cache. Card View will refetch logos using the restored resolver; failed remote images automatically fall back to ticker initials without leaving a broken image.

The monthly-withdrawal KPI row is now custom responsive HTML and shows the complete Positive Months counts without ellipsis.

# v5.9.59 deployment note

Deploy over the existing repository. Saved simulation data and stored PDFs remain protected. Existing saved simulations will rebuild to PDF layout v18 when opened/downloaded so the new yearly cash-flow reconciliation page is used.

# v5.9.58 deployment note

Deploy over the existing repository. Do not delete live saved Portfolio Simulation JSON/PDF state.

The first successful refresh after deployment creates `data/monthly_returns_full_history.csv`. After that, the normal daily refresh automatically grows the annual and monthly historical schema every January as another calendar year becomes complete. No manual yearly code update is required.

# v5.9.57 deployment note

Deploy v5.9.57 over the existing GitHub repository; do not delete the repository or live saved Portfolio Simulation/PDF data.

After the code commit reaches `main`, the normal MarketScope refresh automatically:
1. downloads adjusted daily history from the 2000 anchor;
2. writes the 25 completed annual-return columns used by Market Table;
3. writes `data/monthly_returns_25y.csv` with actual month-end returns for 2001-2025;
4. validates that each comparable set of 12 monthly returns compounds back to its Market Table annual return within 0.05 percentage points;
5. persists annual + monthly source data with the race-safe v5.9.55 persistence mechanism;
6. rebuilds the existing 10Y actual-monthly and recession ranking datasets.

No manual monthly-history or 25Y repair action is required.

# v5.9.55 deployment note

After uploading v5.9.55 over the existing GitHub repository and committing to `main`, the normal MarketScope refresh will:

1. generate the full automatic 25Y snapshot;
2. validate 2025–2001 annual-return coverage;
3. immediately persist the verified snapshot with race-safe retries;
4. generate the monthly/recession ranking datasets;
5. persist those rankings separately with the same race-safe retries.

Do not delete the existing repository before deploying. Preserve the live saved Portfolio Simulation JSON/PDF files and the existing GitHub token configuration.

# MarketScope v5.9.40 - Final Deployment Notes

Parent release: MarketScope v5.9.38.

## Change
Portfolio Simulator PDFs now include the annual-withdrawal comparison that was already available in the app:

1. Strategy comparison page
   - Annual withdrawal
   - Rebalanced remaining balance
   - Not-rebalanced remaining balance
   - Rebalance difference
   - Year-by-year side-by-side return and remaining balance
2. Detailed Rebalanced annual-withdrawal schedule
3. Detailed Not Rebalanced annual-withdrawal schedule

Each detailed table includes Year, Starting Balance, Portfolio Return, Gain/Loss, Balance Before Withdrawal, Withdrawal, and Remaining Balance.

Older saved simulations are rebuilt into the v8 PDF layout when opened. Records saved before both strategy schedules existed fall back safely to the legacy not-rebalanced schedule.

## QA
- Full automated suite: 178 passed.
- Sample PDF generated and rendered successfully.
- Pages 3-5 visually inspected for clipping, overlap, and readability.


## v5.9.46
- Added Top 100 Rebalanced Monthly and Not Rebalanced Monthly 10Y presets ($300K start / $5K monthly / HWM excluded / four different sectors).
- Renamed annual withdrawal UI to Yearly withdrawal and added mutually exclusive Monthly withdrawal controls.
- Portfolio PDFs now include full month-by-month strategy results when monthly withdrawal mode is saved.
- PDF layout contract upgraded to v9; saved-PDF persistence protections remain unchanged.


## v5.9.46 deployment requirement

After pushing this release to `main`, confirm the GitHub Actions workflow completes successfully. It now builds the durable 120-month adjusted-return dataset and regenerates both Top 100 monthly-withdrawal rankings from actual monthly market history. The app rejects older approximate monthly ranking CSVs until an actual-monthly refresh is available.
