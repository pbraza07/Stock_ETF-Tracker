# v5.11.27 - Conflict-safe macro snapshot publishing

Confirmed run: https://github.com/pbraza07/Stock_ETF-Tracker/actions/runs/34960969107
The FRED key works: all three sources were Updated. The save step failed with
an add/add rebase conflict in data/macro_snapshots/USPHCI.json.

The new publisher starts from the latest remote head in a temporary worktree,
compares validated retrieval timestamps, keeps newer remote snapshots, commits
only the three allowed snapshot files, and retries non-forced pushes if main moves.
It never rebases the generated JSON commit or overwrites unrelated app/user files.
All v5.11.26 retry/fallback and v5.11.25 YTD features remain included.

IMPORTANT: replace .github/workflows/update_macro_snapshots.yml as well as
scripts/publish_macro_snapshots.py. The save step must now say:
python scripts/publish_macro_snapshots.py

After uploading, use Actions > Refresh macro snapshots > Run workflow on main.
Do not choose Re-run jobs on the old failed run: that uses its older commit.
Keep the working FRED_API_KEY secret. No new secrets are needed. Preserve all
existing data and PDFs when upgrading. Local tests do not prove production push
permissions; verify the new workflow run and resulting snapshot commit.
