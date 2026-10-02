# MarketScope 5.11.53 — Saved news by stock

Market News now includes a searchable **Stock referenced in saved news** dropdown.
Options show ticker, company name, and number of saved stories. They are built
from the entire archive, including old and neutral articles, rather than only
the current page or date window.

Selecting a stock resets the date to All archived news, includes every source
and impact direction, clears text search, and returns to page one. All matching
articles are available using the existing pagination. Additional filters can
then narrow the selected stock's stories. Choose All stocks / all news to clear
the stock selection. Collection and refresh behavior remain unchanged; stock
selection itself does not trigger a new provider request.

Stock identification uses saved headlines and publisher excerpts and the same
tracked stock universe as news cards. Unknown companies, unrecognized aliases,
and references only present in article bodies are not guessed. A story may
appear under multiple stocks. Historical archives are indexed automatically
without requiring another download or a migration.

No new dependencies, credentials, or deployment settings are needed. This
cumulative package excludes live archives and saved portfolios. Preserve your
deployed data when uploading. The update has not been deployed to the live app
by the assistant. Automated checks are recorded in validation/.
