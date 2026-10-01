# MarketScope 5.11.50 — Story-specific impact and summaries

Each news card now starts with independent Stock, Sector and Overall U.S. Market impact badges. Green ▲ means potentially bullish, red ▼ potentially bearish, gray ↔ neutral/unclear; mixed evidence uses yellow ↕. Every label is low confidence, derived from the headline and short source feed excerpt. Neutral means insufficient directional evidence, not proof of no effect.

The highlighted summary button now contains only the specific publisher news excerpt, without generic risk-appetite or classification boilerplate. A five-line CSS clamp keeps previews compact at mobile widths; clicking opens the reader with the available excerpt and individual impact explanations. Long previews end visually at the clamp; truncated feed excerpts are marked with an ellipsis. This is a concise feed preview, not an AI paraphrase or full linked-article analysis.

Tracked stocks are identified from the existing local universe using company names and explicit ticker mentions. Stocks outside that universe may remain unidentified. Sector labels use universe mappings and explicitly mentioned sector terms. A company signal is not automatically propagated to its sector or the overall market. Overall-market filters and counts now use the independently evaluated market scope.

Newly collected archive records include scoped impacts, summary text and analysis basis. Existing archived stories render the new assessment immediately without deleting history. Prior calendar functionality, tab order, manual 13-feed refresh, automatic collection and portfolio tools remain intact.

Validation: 41 targeted news tests passed, including issuer/sector/market separation, opposite issuer signals in one headline, uncertain news, supplier/customer ambiguity, old-archive rendering and repeated manual refresh. Live browser typography and publisher delivery have not been verified. Not deployed.
