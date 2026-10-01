# MarketScope 5.11.51 — Five-line full-article summaries

Adds allowlisted public article retrieval, extraction of all accessible article-body text, and optional AI paraphrasing into exactly five short lines. Completed summaries replace the feed-only preview, appear in the reader, and save in the existing archive. No generic market commentary is inserted into the summary.

Requires OPENAI_API_KEY and MARKETSCOPE_NEWS_SUMMARY_MODEL. Setup, scheduled batches, API usage and extraction limitations are documented in FULL_ARTICLE_SUMMARIES.md. Without configuration or source access, feed-only previews are explicitly labeled. No live model/provider validation or deployment has been performed.

Paywalls, access challenges, partial/unrecognized bodies, oversized articles and invalid model responses fail visibly without substituting a headline-only summary. Existing news labels, tabs, archive and portfolio features remain available.

Validation: 46 targeted tests passed, covering full-body inclusion, paywall rejection, five-line output validation, model request payloads, scoped impacts, archived readers and manual refresh. Model/network calls in tests are mocked.
