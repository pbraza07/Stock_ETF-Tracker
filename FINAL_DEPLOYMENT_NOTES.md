# MarketScope v5.2 deployment notes

**Root cause fixed:** v5.1 shipped blank generated CSVs. Uploading the package replaced a previously successful 4,000+ instrument GitHub snapshot with the blank 41-row bootstrap snapshot. The daily GitHub Action could repopulate it, but there was a temporary period where all stock return percentages appeared blank; direct Yahoo requests from Render could also be throttled.

**v5.2 fix:** generated market data is no longer part of the upgrade payload. Bootstrap files have distinct names and cannot overwrite durable server data. The app loads generated local data first, falls back to the durable GitHub snapshot when needed, and manual refresh seeds from GitHub before contacting Yahoo.

Upgrade by uploading v5.2 on top of the existing GitHub repo. Do not delete the three generated files first.

Automated refresh remains 6:00 PM America/New_York every day. All app timestamps remain U.S. Eastern.
