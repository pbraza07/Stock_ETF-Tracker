# MarketScope 5.11.36 — Projection completion and memory fix

## Changes

- Forward Planning uses temporary disk-backed scenario arrays and calculates planning-return adjustments one month at a time instead of allocating full-size intermediate copies.
- Monthly balance histories are retained only where stress-test recovery calculations need them. Normal projection summaries, percentiles and tables are unchanged.
- Projection jobs run independently of the Streamlit page runner. The page polls a small status fragment every three seconds rather than blocking in a tight polling loop.
- Only one heavy projection runs at a time per server process. Additional submissions receive an explicit busy message instead of multiplying memory use.
- Run/Reset controls are disabled while a job is running. Completed results populate the existing results view and session cache. Failed or missing jobs release the UI for another attempt.
- Progress explicitly reports forecast months and the current calculation stage. A counter such as 85/120 is no longer described as the number of simulations completed.
- The selected 50,000-path simulation count is preserved. Financial assumptions, random seed, expected returns, withdrawals, RB/NR formulas and export interfaces are not intentionally changed.

## Validation

- Full regression suite: 687 passed, 71 warnings, approximately 24 seconds. Warnings include pre-existing numerical and deprecation warnings; no failed tests.
- New tests cover exact disk/in-memory scenario equality, balance-capture equivalence, concurrent-job rejection, failed-job recovery, completed-result UI handoff/cache and missing-worker control recovery.
- Local end-to-end synthetic-fixture benchmark: four holdings, ten years, 50,000 paths, both strategies and default planning diagnostics/withdrawal solving, seed 1234. Solver retains its existing separately disclosed 1,000-path subset; it is not claimed to run 50,000 solver paths.
- Version 5.11.35: 21.23 seconds, maximum resident set 868,628 KiB (848 MiB).
- Version 5.11.36: 18.95 seconds, maximum resident set 396,420 KiB (387 MiB), approximately 54% lower peak process memory.
- Both benchmark processes used OPENBLAS_NUM_THREADS=1. These are local engine measurements, not live Render capacity or browser load tests. Disk/file-cache memory and the app's other workloads also affect deployment limits.

## Connection error and remaining limits

The screenshot reports an HTTP 429 connection failure, not a Python calculation exception. Its originating service cannot be determined from the screenshot. This release fixes confirmed excessive allocations and page-runner coupling; it does not claim that all HTTP 429 responses are caused by memory pressure or can be fixed inside the calculation engine.

Jobs survive ordinary page reruns and brief reconnects that retain the same Streamlit session and server process. They do not survive a server restart or a new browser session. No automatic retry creates duplicate jobs. Inactive completed jobs expire after 30 minutes when another job is submitted. Temporary scenario files contain simulated data and are removed after success or failure.

If HTTP 429 persists, inspect Render runtime/proxy logs at the failure timestamp for request limits, restarts, memory exhaustion or provider failures. Do not assume a refresh or repeated click will resolve it. The repository still specifies a free Render plan; this update does not purchase or change hosting plans.

## Install

Upload/merge the archive's repository-root files into Stock_ETF-Tracker and deploy the new commit. Preserve existing secrets, durable saved simulations, market snapshots and generated reports. The archive excludes these live data files. Confirm the app displays version 5.11.36 before testing.

This release package has not been pushed to GitHub or deployed to Render from this workspace.
