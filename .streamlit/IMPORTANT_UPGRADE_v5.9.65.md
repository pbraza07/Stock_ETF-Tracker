# MarketScope v5.9.65 — Manual Nasdaq Universe Refresh

## Why “Pending first successful universe refresh” can appear

Release ZIPs intentionally do not overwrite the generated `data/universe_metadata.json` file. A fresh repository starts with `universe_metadata.bootstrap.json`, whose timestamp is blank. The dashboard therefore remains pending until a real universe refresh is successfully persisted.

Earlier workflows also saved `universe_metadata.json` only after the much longer Yahoo/history verification pipeline. If a later history, Stooq, monthly reconciliation, or ranking step failed, the Nasdaq universe step could have succeeded but its timestamp still never reached GitHub.

## v5.9.65 fixes both paths

1. The scheduled workflow now persists `data/default_universe.csv` and `data/universe_metadata.json` immediately after `scripts/update_universe.py`, before the long history pipeline.
2. Market Navigator now includes **↻ Refresh Nasdaq Universe Now**.

The button runs the same Nasdaq universe generator used by GitHub Actions, updates the >$100B membership, analyst ratings, added/removed symbols, rating changes, and the Last Refreshed timestamp, then saves the generated universe + metadata to GitHub using the existing `MARKETSCOPE_GITHUB_TOKEN` Contents read/write permission.

If the token is unavailable, the manual universe refresh still updates the current Render process, but it is not durable across a Render restart.

## What the button does not rebuild

The universe button intentionally does not run the full historical/ranking pipeline inside the Streamlit web request. Use the existing **Entire tracked universe** manual market refresh for prices/history on the current app, while the scheduled 6 PM ET workflow remains responsible for full monthly-history verification and Top ranking regeneration.
