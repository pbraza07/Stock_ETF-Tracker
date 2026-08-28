# FIX NOTES v5.9.18

- Adds a dynamic Nasdaq universe status strip showing the latest universe refresh timestamp in U.S. Eastern time.
- Tracks stocks added and removed during the Eastern calendar day as the >$100B Nasdaq market-cap screen changes.
- Persists `data/universe_metadata.json` in the scheduled GitHub Action so Render displays the same status across devices/restarts.
- Saved portfolio simulation records now include instrument name, sector, analyst rating, and Low/Average/High analyst price targets.
- PDF page 1 now contains a compact `PORTFOLIO INSTRUMENT / ANALYST SNAPSHOT` table with those fields while preserving combined portfolio analytics/timeframes.
- Up to 8 instruments are shown on page 1; if a portfolio contains more, the PDF explicitly notes that complete instrument detail follows.
