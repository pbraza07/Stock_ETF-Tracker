# MarketScope 5.11.52 — Auditable news keyword library

## Changes

- Added a versioned phrase-family library in `news_keywords.py`. Patterns cover price action, earnings surprises, business growth, guidance, losses, profitability, credit, liquidity, capital returns, dilution, contracts, operations, product safety, legal outcomes, regulation, governance, analyst ratings, and macro ambiguity.
- Green means potentially bullish; red means potentially bearish; gray means neutral/unclear or conflicting evidence. These are LOW-confidence wording classifications, not verified causal effects or return forecasts.
- Cards explicitly identify matched company names, tickers and sectors. Company-specific direction is not propagated to the sector or overall market.
- Reader lists matched wording and rule explanations. The News keyword library & indicator rules expander supports searching and downloading all rules as JSON.
- Existing archived headlines are interpreted using the updated rules when viewed; existing articles and summaries are preserved.

## Interpretation and limits

No finite library contains all possible wording. Each regular expression represents a family of variants, not a predictive model. Unsupported, negated, speculative or conditional wording abstains. Conflicting positive/negative evidence is shown as neutral/conflicting; it is not resolved by counting words.

Analysis uses headlines and short publisher feed excerpts, not full article bodies or generated AI summaries. It can miss information, sarcasm, implied subjects, aliases and narrative nuance. A reported price move describes something that happened, not an expected future move. Macro effects depend on expectations and economic context.

Entities come from the bundled stock universe, with company-name and ticker matching. Unknown companies remain unidentified; ambiguous short tickers require explicit notation. Sector classifications reflect the source universe and may be stale. Company mention does not prove the story is primarily about that company. This is not comprehensive entity recognition or professional investment advice.

## Upgrade

Deploy this cumulative package using the existing workflow. No new API keys or dependencies are required for keyword classification. Existing optional full-article summary configuration is unchanged. Preserve deployed user data; the package excludes live news archives and portfolio save data.

This release has not been deployed or verified on the live service by the assistant. Automated validation results are included under `validation/`.
