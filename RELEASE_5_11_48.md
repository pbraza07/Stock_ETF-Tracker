# MarketScope 5.11.48 — Market News

- New Market News tab and a direct button on Market Navigator.
- Thirteen curated RSS feeds from twelve financial publishers and official agencies; per-source health/freshness reporting.
- Publication dates in Eastern Time, three-part clickable summaries, in-app reading panel and original-source links.
- Green ▲ / red ▼ potential-effect labels with transparent LOW-confidence headline rules. Mixed and unclear evidence is retained. Reported moves are distinguished from potential catalysts.
- Discussion themes, directional counts and clearly conditional upside/downside scenarios; no probability forecast is invented from headline counts.
- Search, source/direction/date filters, pagination and complete JSON archive export.
- Atomic archive writes, URL deduplication, historical retention, failed-source preservation, GitHub merge/conflict handling and optional persistent-disk path.
- Fifteen-minute checks while the tab is open; a separate hourly GitHub Action for unattended gathering after deployment.
- Commercial full articles are not transcribed. Short attributed feed excerpts and MarketScope context are used; eligible original U.S. federal releases can be read and saved in-app.

Validation: 744 automated tests passed (74 warnings), including 30 new news-feature tests. Actual publisher requests timed out in this workspace, so live endpoint availability and mobile rendering have not been verified. The source panel reports partial/unavailable coverage honestly. This ZIP is not deployed.

Read MARKET_NEWS.md for setup, source list, storage configuration, content limitations and classification methodology. Existing simulations, calendar controls and saved portfolio data are preserved. Live news archive data is excluded from the upgrade ZIP.
