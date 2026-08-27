# v5 Final changes

- Fixed direct-script import path for GitHub Actions/Render.
- Render build no longer downloads thousands of historical series.
- Added Nasdaq Analyst Rating column and rating-source timestamps.
- Added green/yellow/red analyst-rating cell formatting.
- Added rating quick filter and advanced filters covering every displayed table column.
- Added persistent snapshot metadata in U.S. Eastern time.
- Scheduled refresh is 6:00 PM America/New_York every day.
- Added manual-refresh instrument counter and percentage progress display.
- Added GitHub-backed durable manual snapshot persistence.
- Manually persisted symbols survive subsequent scheduled refreshes.
