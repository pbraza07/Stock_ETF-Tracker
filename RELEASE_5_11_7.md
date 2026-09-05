# MarketScope 5.11.7 - Top 12 click handoff fix

The prior update protected a background job only after it had been created.
Its button callback selected a category, but job creation still depended on the
button returning True in the body of that same script run. A parent rerun or
interruption between callback and rendering could consume the button event,
leaving no job, no error and the original "Choose a Top 12 button" message.

The callback now saves the category as a pending request immediately. The UI
consumes that request on its next render, starts exactly one job, and clears the
request only after job creation. Both buttons retain their existing labels and
scoring formulas. Results, progress, error messages and background persistence
remain as introduced in 5.11.6.

Regression tests now explicitly interrupt execution after each category's callback
but before the ranking body runs. The next run has no button pulse. Both categories
must still launch once, display 12 rows and avoid duplicate jobs on further reruns.
These cases reproduce the missed handoff in 5.11.6 and pass with this patch.
Full regression results are included in `validation/pytest.txt`.

Install the extracted files at the repository root, preserve deployed data, and
redeploy on Render. Confirm **5.11.7** in the app before retesting. No dependency,
environment-variable, historical-simulator or scoring changes are required.

This package has not been deployed to or tested inside your production Render
instance. Server restarts/new browser sessions still end in-memory jobs. Existing
data-quality and historical-backtest limitations are unchanged.
