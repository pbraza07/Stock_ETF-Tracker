# MarketScope v5.11.58 — Market-loading crash fix

The reported `KeyError: 'Type'` occurs when a market-dependent screen receives a schema-less empty DataFrame. The lazy-loading path previously decided whether to load market data before Streamlit registered/resolved the active tabs. Navigation and data loading could therefore disagree. The skipped-data branch explicitly created a DataFrame without columns. Empty universes and partial snapshot/session rows were additional unguarded inputs.

Changes:
- Register one stable top-level tabs container before market loading. Determine the workspace from its actual open tab, not an earlier state lookup.
- Use the same container identity when focusing Future Projection, avoiding a default-dependent widget reset.
- Preserve the complete market schema for empty universes and workspaces that skip market loading.
- Merge known instrument metadata, saved snapshot evidence, and session overlays without deleting fields absent from a partial overlay.
- Handle snapshots without Symbol and duplicate ticker rows safely. Unknown classifications remain Unknown, and missing returns/prices remain missing; no financial values are invented.
- Display a clear empty-data message in Market Navigator.
- Preserve v5.11.57 session results, portfolio tools, calendars, news, projections and reports.

Validation: five new regression tests cover empty/partial/malformed/duplicate snapshots, session overlays, and actual tab navigation/data-loading selection. The existing navigation tests now verify one stable container, with Market News first and Alerts & Help last. Full suite: 831 tests.

Deployment: install this package in the existing repository and deploy the updated source to Render. Confirm the displayed version is 5.11.58. This package has not been deployed to the live service during preparation. It contains no user-generated session data or credentials.
