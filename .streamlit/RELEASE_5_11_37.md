# MarketScope 5.11.37 — Production connection resilience

## What was verified

GitHub and the live app were both on 5.11.36 on September 21, 2026. The app health and host-config endpoints returned HTTP 200, and Future Projection loaded in a live browser. The reported HTTP 429 was not reproduced. Its source remains unconfirmed; no claim is made that a calculation change alone can eliminate a hosting/proxy rate limit.

The deployed configuration still enabled automatic file-change reruns and used Streamlit's default two-minute disconnected-session retention. The earlier successful numerical benchmark used one BLAS thread, but production did not enforce that setting. These are concrete configuration gaps addressed here, not proof of the original 429's cause.

## Changes

- Production startup explicitly limits numerical thread pools to one thread by default before importing Streamlit and NumPy. MARKETSCOPE_NUMERIC_THREADS is the deliberate override, constrained to 1–8.
- Disable production file watching and automatic file-change reruns.
- Retain disconnected sessions for 30 minutes and configure a 30-second WebSocket heartbeat. This helps reconnects within the same running server; it does not survive server restarts or route around provider rate limits.
- Log projection start/completion/failure timestamps, elapsed time and an abbreviated job identifier. Logs do not include holdings, balances, secrets or full job tokens.
- Add scripts/check_connection.py, a single-pass health/host-config check capturing status and provider request IDs without cookies. It stops on 429 and does not retry around rate limits.
- Preserve 5.11.36 background jobs, single-active-job limit and memory fixes. No intended financial calculation or simulation-count changes.

## Required Render deployment step

1. Merge the archive's contents into the repository root, including the .streamlit folder. Preserve existing live datasets, saved simulations, reports and secrets.
2. In Render, open the MarketScope service, then Settings → Build & Deploy → Start Command.
3. Set the command to: `python start_marketscope.py`
4. Deploy the latest commit. render.yaml contains this command too, but an existing manually configured service may not apply a YAML change automatically.
5. Verify the startup log contains `MarketScope production startup: numeric_threads=1; disconnected_session_ttl=1800s; file_watcher=none` and the app displays v5.11.37.
6. Open a fresh app tab after deployment and run the projection once. A deployment itself interrupts existing connections.

No hosting-plan purchase, security-policy relaxation, GitHub push or Render deployment was performed from this workspace.

## If HTTP 429 recurs

Capture Render runtime logs at the exact failure time. The decisive evidence is whether there is a process restart/out-of-memory termination, a recorded completed/failed projection, or a health/host-config request rejected upstream. A 429 does not by itself prove the simulation ran out of memory.

For an independent lightweight probe, run:

`python scripts/check_connection.py https://marketscope-stock-etf-tracker.onrender.com`

The probe cannot reproduce a mobile-only issue or establish that a healthy request now proves there was no earlier outage. Check provider request IDs with Render support when appropriate. Do not repeatedly refresh or submit while a rate limit is active. The code cannot override hosting quotas or provider access controls.

## Validation

Full automated suite: 690 passed, 71 warnings. Streamlit loaded and returned the intended four production configuration values. Tests cover numerical thread configuration, production startup flags, session/job recovery from the preceding release and stopping diagnostics after 429. The production-configured 50,000-path benchmark is recorded in validation/production_benchmark_v51137.json. It is a local synthetic four-holding/ten-year benchmark, not a live Render load test; sustainable-withdrawal solving retains its existing disclosed 1,000-path subset.

References: https://render.com/docs/websocket and https://docs.streamlit.io/develop/api-reference/configuration/config.toml
