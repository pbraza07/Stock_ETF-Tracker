# MarketScope 5.11.14

YTD history now requests dates explicitly from December of the previous year and aligns each holding's trading dates before joining. When no shared prior-year close is available, simulation starts at the first shared current-year close and visibly identifies Partial YTD and its actual start date. Missing holdings or fewer than two observations still produce a specific error; prices and earlier returns are never fabricated.

Results show beginning balance, current balance after withdrawals, positive trading days and positive observed months. Positive-period counts use compounded investment returns before withdrawals and include the current partial month.

Save YTD simulation stores both strategies, inputs, dates, balances, counts and result tables through the existing saved-simulation persistence mechanism. Saved / Manage displays these snapshots without recalculation. Local-only persistence is explicitly reported when GitHub saving is unavailable.

Existing historical simulation calculations and PDF templates are unchanged. Deploy the archive contents at repository root while preserving existing live data. This package has not been deployed to Render.
