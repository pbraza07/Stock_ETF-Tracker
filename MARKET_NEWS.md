# Market News · 5.11.50

## Reader and market context
The first top-level Market News tab supplies publication dates (Eastern Time), a clickable story-specific preview (maximum five visible lines), in-app context reader, green ▲ / red ▼ potential-impact labels, mixed/unclear labels, original links, search and publisher/direction/time filters. Twenty stories per page keep mobile use manageable. Preview text is clamped to five visible lines, with the available excerpt shown in the reader.

Source coverage: 13 curated RSS endpoints from 12 publishers/agencies: CNBC (Markets and Economy), BBC, The Guardian, Financial Times, Wall Street Journal, MarketWatch, Yahoo Finance, Investing.com, Federal Reserve, BLS, BEA and ECB. Endpoint availability is shown individually, not assumed. This workspace could not complete direct feed requests (timeouts); live collection must be verified after deployment. No static sample stories are shipped.

The summary box uses the publisher's short feed excerpt (maximum 25 words), without generic commentary. It is a source-specific preview, not full-article analysis or an AI-generated paraphrase. Separate Stock / Sector / Overall U.S. Market badges classify potential effects using headline/excerpt evidence. Company names and tickers are resolved against the tracked universe; unidentified names remain neutral. Company news does not automatically determine sector or market direction. The reader explains each scope. Repeated exact headlines count once in discussion totals; different headlines covering the same event can still bias counts.

The reader does not reproduce copyrighted commercial articles or bypass subscriptions/paywalls. Original U.S. federal releases from allowlisted Fed/BLS/BEA release pages may be loaded and archived as plain text. Extraction failures link back to the official page. Text is limited to 100,000 characters and marked if truncated. Attribution remains attached.

## Collection and retention
- Opening Market News checks feeds when the last attempt is at least 15 minutes old. While the tab remains open, a Streamlit fragment checks every 15 minutes. The Pull all 13 news feeds now button fetches all configured feeds immediately, independently of the automatic freshness interval. Simultaneous collectors within the app process are prevented. Browser closure stops that fragment.
- The included `Archive market news` GitHub Action runs hourly at :23 UTC, subject to GitHub scheduling delays, and can be run manually. It only starts once installed on the repository's default branch with Actions enabled.
- Every collected item is archived automatically by canonical URL, with first-seen, last-seen, published date, source, short excerpt, summary, model basis, and optional agency text. Duplicate URLs update instead of multiplying; articles absent from later feeds remain. Cross-feed repeated URLs are one record. Collection starts when enabled; it cannot recover all historical news that has rolled off a feed.
- Local JSON uses atomic replacement and a file lock on Linux. Corrupt archives are not overwritten. Failed sources retain their last success timestamp and previously saved stories.
- GitHub writes merge remote records and retry SHA conflicts rather than overwriting another collector's additions. No deletion or automatic retention cutoff is applied.
- Export the complete archive as JSON inside the tab.

## Render configuration
Use `MARKETSCOPE_GITHUB_TOKEN` (existing fine-grained token with Contents read/write on the repository) for automatic durable GitHub mirroring of interactive collection. The repository and branch use existing `MARKETSCOPE_GITHUB_REPO` / `MARKETSCOPE_GITHUB_BRANCH` variables. GitHub Actions uses its built-in token.

Alternatively set `MARKETSCOPE_NEWS_ARCHIVE` to a JSON file on a mounted persistent disk, for example `/var/data/market_news_archive.json`. By default it is `data/market_news_archive.json`. Local saves on an ephemeral Render disk can disappear on redeployment; the app discloses local-only or failed mirroring. The release ZIP excludes the live archive so an upgrade cannot replace it.

GitHub has repository-file size limits; if reached, the app reports sync failure and retains local data. Use a persistent disk and download backups as the archive grows. News-only commits include `[skip render]` to avoid rebuilding Render on each collection (https://render.com/docs/deploys#skipping-an-auto-deploy). The app reads the updated archive without a deployment.

## Direction methodology
Labels are LOW-confidence interpretations, never guarantees. Narrow headline patterns recognize reported broad-index moves, certain earnings-guidance revisions, inflation direction and explicit distress. Questions, negation and speculative language abstain. Conflicting matches are mixed. Unknown stories are retained without a forced red/green label. Rates, jobs and commodity news are not automatically bullish or bearish. Scenario descriptions are conditional frameworks, not calculated forward market probabilities.

## Validation and limits
Automated tests cover RSS/Atom, unsafe XML/URLs, undated stories, bearish/bullish/mixed/negated headlines, bounded excerpts, archive merge/retention/concurrency and failure handling, in-app display and release integration. Live publisher availability and iPhone layout need a deployment check. No API key is required for the configured public RSS feeds; publisher rate limits and changes can cause partial coverage.
