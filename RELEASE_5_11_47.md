# MarketScope 5.11.47

Calendar navigation now runs inside the browser panel. Back replaces the earnings iframe with a fresh economic iframe without a Streamlit callback, fragment rerun, market-data fetch, or WebSocket round trip. Each switch destroys the previous iframe. The economic widget URL, dark filter, earnings sandbox and adjustable cropping remain intact.

The panel shows the current Monday–Sunday date range in America/New_York. IMPORTANT: automatic earnings This Week / United States / importance filtering is NOT implemented by the provider iframe. Inspection of Investing.com's current earnings frontend found its own filter state and timeframe handling rather than the economic widget parameters. Select This Week inside the provider calendar; set Top crop to zero if controls are obscured. No claim is made that the copied URL parameters enforce filters.

Validation includes repeated navigation and crop changes by executing the actual panel JavaScript in Node with a DOM test double, and a Streamlit mount test. Live iPhone/provider rendering has not been verified. This package has not been deployed.
