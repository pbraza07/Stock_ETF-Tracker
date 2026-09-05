# MarketScope v5.9.80 — Refresh Persistence Execution Fix

## Fixed

The GitHub Actions refresh was stopping with exit code 126 at the first persistence checkpoint because `scripts/persist_generated_files.sh` did not retain an executable file mode after packaging/deployment.

All workflow calls now run the helper explicitly through `bash`, so the refresh no longer depends on the executable bit. The verified annual/monthly history and ranking stages can now run after the universe refresh.

## Monthly ranking protection

The actual-monthly Rebalanced and Not-Rebalanced Top 100 CSVs are now persisted immediately after they are generated. A later failure in the independent recession-ranking stage can no longer discard completed monthly rankings and cause the Portfolio Simulator to show the unavailable-data warning.

## Deployment

Deploy this version to `main`. Its push-triggered workflow will generate and save the missing actual-monthly history and both monthly Top 100 ranking files. A browser reload only reads already-generated files; it does not itself run the GitHub Actions ranking workflow.
