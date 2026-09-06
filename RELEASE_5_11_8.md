# MarketScope 5.11.9

Fixes the Top 12 loading/completion path shown in the reported screenshot.
Remote history loading now has a shared three-second overall wait, with local
history retained for ranking stability when the remote source is slow.
Monthly and live supplemental waits are bounded at five and eight seconds.
If unavailable, the existing ranking engine uses its disclosed historical fallback.
Actual computation time depends on server capacity and universe size.

The result table is rendered by the same fragment that checks job completion.
It does not request a full-app rerun to reveal the table. Category buttons remain
available during calculation. History writes use a separate executor so a slow
save cannot occupy a ranking worker. Existing calculations are unchanged.

Validation includes delayed history, both category tables, completed-job polling
without a full-app rerun, retention through navigation, and export/save failures.
The cloud browser blocked localhost access; live Render and visual browser
verification have not been completed. This ZIP does not deploy itself.

Deploy the extracted contents at the repository root, preserving existing data
and server history. Redeploy Render and confirm the app shows 5.11.9. No new
environment variables or dependencies are required. Earlier backtest validation
limitations remain unchanged.
