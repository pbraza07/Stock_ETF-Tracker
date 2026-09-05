# MarketScope 5.11.6 - Top 12 results display fix

This is a targeted fix based on the delivered 5.11.5 package. The previous ZIP
is preserved. No historical simulation or ranking-score formulas were changed.

## Fixed result flow

Previously the UI ran the entire operation under a transient button state and
waited for remote history persistence before rendering the table. That flow was
vulnerable to interruptions and unnecessary network delays. We cannot identify
the exact production trigger without the deployed server logs.

Now a session-owned background job continues across normal Streamlit reruns and
tab changes. A polling status shows the current phase and displays the completed
table automatically. Each button selects its respective view and keeps Favorite
Picks open. Duplicate submissions are disabled while a job is pending. The job
does not survive a server restart or a new browser session.

Completed results are retained before history is saved in the background. History
load/save failures, malformed event records and PDF/Excel generation failures no
longer discard the table. The previous result remains visible when a calculation
fails, together with an actionable error. Details go to server logs.

Supplemental monthly input waits are bounded at 15 seconds and recent-market
inputs at 45 seconds; if unavailable, the ranking uses explicitly labeled fallback
data. Provider requests already running may finish in the background. The existing
historical evidence and sector-diversity requirements still apply: the application
does not invent 12 picks if the required eligible stocks do not exist.

## Validation and installation

Automated Streamlit tests click each button in a lazy-tab harness and assert that
the selected view contains 12 rows. Tests cover failed exports/saves, pending-job
reruns, tab switching, visible errors and slow-source fallback. The actual ranking
worker is also tested with offline historical inputs. The full regression result
is included in `validation/pytest.txt`.

The production Render instance has not been deployed or browser-verified in this
run. The earlier model-validation/data-history limitations remain unchanged.

Upload the ZIP contents into the GitHub repository root, preserving deployed
data and history files; deploy that commit on Render. Confirm the app displays
**5.11.6**, open **Favorite Picks**, and click either Top 12 button. No environment
variable or dependency changes are required. Existing `render.yaml` settings apply.

Main changed files: `top12_jobs.py`, `top12_ui.py`, version metadata, documentation
and the new `tests/test_v5116_top12_results.py` interaction tests.
