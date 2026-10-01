# MarketScope 5.11.33 — Future Projection macro recovery

Future Projection now uses FRED_API_KEY from the server environment for its 11 configured macro series. Successful downloads are cached for six hours. Public CSV is a fallback; if retrieval fails, the last successfully saved observations remain available with a stale status. Failed downloads do not overwrite valid observations. API credentials are never stored in source URLs or diagnostic messages.

The Macro freshness row now reports Available, Partial, Stale or Unavailable, coverage out of 11 series, observation-date range, and retrieval time. Monthly/quarterly observation dates are not treated as download timestamps. An entirely missing macro feed is no longer labeled Latest Available. Cached whole-projection contexts are labeled Cached separately.

Setup: set FRED_API_KEY in Render → service → Environment. A GitHub Actions secret alone is not available to Render. Redeploy the extracted source, preserve existing data, and refresh live projection data / run a new projection. Existing saved simulation snapshots retain the data status they had when generated.

Cache files are under data/macro_cache and require persistent storage to survive Render filesystem replacement. This patch does not add these 11 series to the separate three-series GitHub recession snapshot workflow. No guarantee is made that FRED will always be reachable; live authenticated retrieval in your Render instance remains to be verified after deployment.

Model calculations, Historical-Calibrated behavior, and the recession charts are unchanged. Regression results are in validation/pytest_v51133.txt. GitHub and Render have not been modified by this package.
