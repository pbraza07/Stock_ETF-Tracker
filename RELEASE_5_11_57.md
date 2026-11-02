# MarketScope 5.11.57 — Session result retention

Completed research is retained independently of pending calculations and input widgets.

- Future Projection keeps the completed result visible while a replacement runs, fails, or is cancelled. Loading or clearing draft holdings does not erase it; explicit Reset does.
- Quality research retains completed screening and portfolio results during queued work, failed submissions, tab navigation, and subsequent screenings. Completed portfolio holdings are identified separately from draft selections.
- Sector-leader portfolios retain their original allocation and result when the market snapshot or draft inputs change. Switching ranking families no longer hides completed analysis. A failed saved-ranking source refresh falls back to the session's last successfully loaded table.
- YTD inputs have persistent widget keys. An invalid or failed run leaves the previous result, report record, and completed inputs intact. All three are committed together after successful calculation.
- Build Simulation commits only complete results, including withdrawal availability. Invalid inputs or missing data show the previous completed snapshot, and Saved / Manage uses that snapshot. A partial universe refresh does not delete selected symbols.

Financial formulas and ranking criteria are unchanged. Retained results show their completed inputs/data dates; retention does not make old observations current.

Scope: normal Streamlit session reruns and app-tab navigation, not permanent saving. Closing a browser tab/window ends access to its session; server cleanup can be delayed. A full browser reload, lost session, or server restart may create a new session. Existing Save controls and private calculation recovery remain available for longer-lived retention. This release does not promise browser-close detection or recovery from every disconnection.

Validation: original 820-test suite plus six Streamlit regression tests covering tab navigation, invalid and failed replacements, queued research, pending projections, ranking refresh/kind switching, explicit reset, and session isolation. Provider inputs are mocked for deterministic UI tests; this is not a live mobile/browser load test.

Deployment: replace the application source with this release and deploy through the existing workflow. No secrets or user session data are included. No live deployment was performed while preparing this package.
