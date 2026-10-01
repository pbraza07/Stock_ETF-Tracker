# Full-article summaries — 5.11.51

MarketScope can now read the accessible original article body and create five short, original summary lines. It no longer calls a clipped feed excerpt a full-article summary. Completed summaries appear in the card and reader, remain linked to the source, and are saved in the news archive.

## Enable on Render
Add these environment variables to the MarketScope service:

- `OPENAI_API_KEY`: your OpenAI API key. Keep it in Render secrets, never in source code or chat.
- `MARKETSCOPE_NEWS_SUMMARY_MODEL`: `gpt-4.1-mini`, or another model supporting the Responses API and strict structured outputs.

API usage is billed separately by the provider. No live API call was made while producing this release. Without both settings, the app clearly shows that full-article summaries are not configured.

For scheduled summaries, add `OPENAI_API_KEY` as a GitHub Actions repository secret and `MARKETSCOPE_NEWS_SUMMARY_MODEL` as a repository variable. The hourly news workflow attempts three pending articles per run by default. `MARKETSCOPE_NEWS_SUMMARIES_PER_PULL` can be set between zero and five in the workflow environment. Failed items rotate behind unattempted ones. This is gradual collection, not an immediate summary of every archived article.

## User flow
1. Gather news using the existing automatic schedule or manual 13-feed button.
2. For an unsummarized story, choose “Read full article & summarize in five lines.”
3. The app fetches the allowlisted source, identifies the article body and submits all extracted body text to the configured summarizer.
4. A valid five-line response replaces the feed excerpt in the summary box and is archived. The original source link stays visible.

Each line is limited to 20 words. Lines may wrap on a small screen; no part of the five-line summary is hidden by a visual clamp. The reader exposes when the summary was generated and that it is an AI paraphrase. The stock/sector/market arrows remain explicitly based on headline/excerpt rules; they have not been relabeled as full-article analysis.

## Content and reliability
The extractor includes body paragraphs, headings, lists, tables and captions returned in the accessible HTML; it does not load JavaScript-only article bodies. It stops on detected subscription/access restrictions, unrecognized article structure, very short responses or articles over 90,000 characters. It does not bypass paywalls, use hidden subscriber text, silently truncate long articles, or use RSS in place of the missing body.

Automated structure checks cannot prove a publisher returned every paragraph. The model summarizes all extracted public body text, and the original link remains authoritative. Generated summaries can contain errors and should be checked against the source. Only the paraphrase, body hash, word count, model and date are retained; commercial article bodies are not archived or displayed. Article text is sent to OpenAI for summarization with response storage disabled, and treated as untrusted data rather than instructions.

References: https://developers.openai.com/api/docs/guides/structured-outputs and https://developers.openai.com/api/docs/models/gpt-4.1-mini
